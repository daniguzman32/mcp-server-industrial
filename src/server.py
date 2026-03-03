#!/usr/bin/env python3
"""
Servidor MCP para Fachmann — Gestión comercial B2B de automatización industrial.
Marcas representadas: PILZ, OBO Bettermann, CABUR.

Herramientas disponibles:
  - fachmann_buscar_catalogo         Busca productos por texto y/o marca
  - fachmann_consultar_disponibilidad Precio, stock y entrega por SKU
  - fachmann_buscar_contexto_cliente  Perfil + historial completo de un cliente
  - fachmann_registrar_interaccion    Guarda reunión / email / llamada en el CRM
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import aiosqlite
from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/fachmann.db")

MARCAS_VALIDAS = {"PILZ", "OBO", "CABUR"}
TIPOS_INTERACCION = {"reunion", "email", "llamada", "whatsapp", "nota"}


# ── Lifespan: conexión persistente a SQLite ───────────────────────────────────

@asynccontextmanager
async def app_lifespan(app):
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    yield {"db": db}
    await db.close()


_port = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
_host = os.getenv("MCP_HOST", "0.0.0.0")

mcp = FastMCP("fachmann_mcp", lifespan=app_lifespan, host=_host, port=_port)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows_to_dicts(rows: list) -> list[dict]:
    return [dict(r) for r in rows]


def _db_error(e: Exception) -> str:
    return f"Error de base de datos: {type(e).__name__}: {e}"


# ── Modelos de entrada ────────────────────────────────────────────────────────

class BuscarCatalogoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Texto a buscar en descripción, SKU, categoría o especificaciones (ej. 'relé seguridad', 'bandeja', 'bornera fusible')",
        min_length=2,
        max_length=200,
    )
    marca: Optional[str] = Field(
        default=None,
        description="Filtrar por marca: 'PILZ', 'OBO' o 'CABUR'. Omitir para buscar en todas.",
    )

    @field_validator("marca")
    @classmethod
    def validate_marca(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_upper = v.strip().upper()
        if v_upper not in MARCAS_VALIDAS:
            raise ValueError(f"Marca inválida '{v}'. Opciones: PILZ, OBO, CABUR.")
        return v_upper


class ConsultarDisponibilidadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sku: str = Field(
        ...,
        description="Código exacto del producto (SKU), ej. 'PNOZ-S6-24VDC-2NO', 'OBO-TS-60-E-2M', 'CAB-XCMF010'",
        min_length=2,
        max_length=100,
    )


class BuscarContextoClienteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    empresa: str = Field(
        ...,
        description="Nombre o parte del nombre de la empresa o contacto a buscar (búsqueda parcial)",
        min_length=2,
        max_length=200,
    )


class RegistrarInteraccionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    cliente_id: int = Field(
        ...,
        description="ID numérico del cliente. Obtenerlo previamente con fachmann_buscar_contexto_cliente.",
        ge=1,
    )
    notas: str = Field(
        ...,
        description="Resumen de la interacción: temas tratados, acuerdos y próximos pasos",
        min_length=5,
        max_length=2000,
    )
    tipo: str = Field(
        default="nota",
        description="Tipo de interacción: 'reunion', 'email', 'llamada', 'whatsapp' o 'nota'",
    )

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v: str) -> str:
        v_lower = v.strip().lower()
        if v_lower not in TIPOS_INTERACCION:
            raise ValueError(f"Tipo inválido '{v}'. Opciones: {', '.join(sorted(TIPOS_INTERACCION))}.")
        return v_lower


# ── Herramientas MCP ──────────────────────────────────────────────────────────

@mcp.tool(
    name="fachmann_buscar_catalogo",
    annotations={
        "title": "Buscar Catálogo Técnico Fachmann",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def fachmann_buscar_catalogo(params: BuscarCatalogoInput, ctx: Context) -> str:
    """Busca productos en el catálogo técnico de Fachmann (PILZ, OBO Bettermann, CABUR).

    Realiza búsqueda de texto libre en descripción, SKU, categoría y especificaciones,
    con filtro opcional por marca. Útil para redactar propuestas técnicas o verificar
    qué productos están disponibles en el portafolio.

    Args:
        params (BuscarCatalogoInput):
            - query (str): Texto a buscar (ej. 'relé seguridad', 'bandeja portacables', 'bornera fusible')
            - marca (Optional[str]): Filtro de marca: 'PILZ', 'OBO' o 'CABUR'. Omitir para todas.

    Returns:
        str: JSON con lista de productos encontrados:
        {
            "total": int,
            "productos": [
                {
                    "sku": str,
                    "marca": str,
                    "categoria": str,
                    "descripcion": str,
                    "precio_usd": float,
                    "stock": int,
                    "tiempo_entrega_dias": int
                }
            ]
        }
        Retorna mensaje de texto si no hay resultados.

    Examples:
        - "Buscar relés de seguridad PILZ"       → query="relé seguridad", marca="PILZ"
        - "Mostrar catálogo completo OBO"         → query="bandeja", marca="OBO"
        - "Qué borneras tenemos disponibles"      → query="bornera", marca=None
        - "Buscar monitor de velocidad"           → query="monitor velocidad", marca=None
    """
    try:
        db: aiosqlite.Connection = ctx.request_context.lifespan_state["db"]
        like = f"%{params.query}%"

        if params.marca:
            sql = """
                SELECT sku, marca, categoria, descripcion, precio_usd, stock, tiempo_entrega_dias
                FROM productos_catalogo
                WHERE activo = 1 AND marca = ?
                  AND (descripcion LIKE ? OR sku LIKE ? OR categoria LIKE ? OR especificaciones LIKE ?)
                ORDER BY marca, categoria, sku
            """
            args = (params.marca, like, like, like, like)
        else:
            sql = """
                SELECT sku, marca, categoria, descripcion, precio_usd, stock, tiempo_entrega_dias
                FROM productos_catalogo
                WHERE activo = 1
                  AND (descripcion LIKE ? OR sku LIKE ? OR categoria LIKE ? OR especificaciones LIKE ?)
                ORDER BY marca, categoria, sku
            """
            args = (like, like, like, like)

        async with db.execute(sql, args) as cursor:
            rows = _rows_to_dicts(await cursor.fetchall())

        if not rows:
            filtro = f" en marca '{params.marca}'" if params.marca else ""
            return f"No se encontraron productos para '{params.query}'{filtro}. Intente con otra palabra clave."

        return json.dumps({"total": len(rows), "productos": rows}, indent=2, ensure_ascii=False)

    except Exception as e:
        return _db_error(e)


@mcp.tool(
    name="fachmann_consultar_disponibilidad",
    annotations={
        "title": "Consultar Disponibilidad y Precio por SKU",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def fachmann_consultar_disponibilidad(params: ConsultarDisponibilidadInput, ctx: Context) -> str:
    """Obtiene precio, stock actual, tiempo de entrega y especificaciones completas de un producto por SKU.

    Usar para armar presupuestos precisos o confirmar disponibilidad antes de comprometerse con el cliente.
    Si no conoce el SKU exacto, usar primero fachmann_buscar_catalogo.

    Args:
        params (ConsultarDisponibilidadInput):
            - sku (str): Código exacto del producto (ej. 'PNOZ-S6-24VDC-2NO', 'OBO-TS-60-E-2M')

    Returns:
        str: JSON con ficha completa del producto:
        {
            "sku": str,
            "marca": str,
            "categoria": str,
            "descripcion": str,
            "precio_usd": float,
            "especificaciones": str,
            "stock": int,
            "tiempo_entrega_dias": int,
            "disponible_inmediato": bool
        }
        Retorna error con sugerencia si el SKU no existe.
    """
    try:
        db: aiosqlite.Connection = ctx.request_context.lifespan_state["db"]

        async with db.execute(
            """SELECT sku, marca, categoria, descripcion, precio_usd,
                      especificaciones, stock, tiempo_entrega_dias
               FROM productos_catalogo
               WHERE sku = ? AND activo = 1""",
            (params.sku,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return (
                f"Error: SKU '{params.sku}' no encontrado. "
                "Use fachmann_buscar_catalogo para encontrar el SKU correcto."
            )

        producto = dict(row)
        producto["disponible_inmediato"] = producto["stock"] > 0
        return json.dumps(producto, indent=2, ensure_ascii=False)

    except Exception as e:
        return _db_error(e)


@mcp.tool(
    name="fachmann_buscar_contexto_cliente",
    annotations={
        "title": "Buscar Contexto e Historial de Cliente",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def fachmann_buscar_contexto_cliente(params: BuscarContextoClienteInput, ctx: Context) -> str:
    """Recupera el perfil completo de un cliente o prospecto: datos de contacto, estado del lead,
    últimas interacciones y oportunidades de venta activas.

    Usar antes de una reunión, llamada o al preparar una propuesta comercial.
    La búsqueda es parcial, por lo que 'Arcor' encuentra 'Arcor S.A.I.C.'.

    Args:
        params (BuscarContextoClienteInput):
            - empresa (str): Nombre o fragmento del nombre de la empresa o contacto

    Returns:
        str: JSON con coincidencias encontradas:
        {
            "total": int,
            "clientes": [
                {
                    "id": int,
                    "razon_social": str,
                    "contacto_nombre": str,
                    "contacto_email": str,
                    "contacto_telefono": str,
                    "industria": str,
                    "estado_lead": str,
                    "linkedin_url": str | null,
                    "notas": str,
                    "interacciones_recientes": [...],   // últimas 5
                    "oportunidades_activas": [...]      // oportunidades abiertas
                }
            ]
        }

    Examples:
        - "Prepararme para llamar a Arcor"        → empresa="Arcor"
        - "Ver historial de Sistemi"              → empresa="Sistemi"
        - "Buscar contacto Valentina Bruni"       → empresa="Valentina"
    """
    try:
        db: aiosqlite.Connection = ctx.request_context.lifespan_state["db"]
        like = f"%{params.empresa}%"

        async with db.execute(
            """SELECT id, razon_social, contacto_nombre, contacto_email, contacto_telefono,
                      industria, estado_lead, linkedin_url, notas, created_at
               FROM clientes_prospectos
               WHERE razon_social LIKE ? OR contacto_nombre LIKE ?
               ORDER BY razon_social""",
            (like, like),
        ) as cursor:
            clientes = _rows_to_dicts(await cursor.fetchall())

        if not clientes:
            return f"No se encontraron clientes que coincidan con '{params.empresa}'."

        for cliente in clientes:
            cid = cliente["id"]

            async with db.execute(
                """SELECT tipo, notas, fecha FROM interacciones
                   WHERE cliente_id = ?
                   ORDER BY fecha DESC LIMIT 5""",
                (cid,),
            ) as cursor:
                cliente["interacciones_recientes"] = _rows_to_dicts(await cursor.fetchall())

            async with db.execute(
                """SELECT id, descripcion, monto_usd, probabilidad_cierre, etapa, notas_tecnicas, fecha_cierre_estimada
                   FROM oportunidades_ventas
                   WHERE cliente_id = ? AND etapa NOT IN ('closed_won', 'closed_lost')
                   ORDER BY probabilidad_cierre DESC""",
                (cid,),
            ) as cursor:
                cliente["oportunidades_activas"] = _rows_to_dicts(await cursor.fetchall())

        return json.dumps({"total": len(clientes), "clientes": clientes}, indent=2, ensure_ascii=False)

    except Exception as e:
        return _db_error(e)


@mcp.tool(
    name="fachmann_registrar_interaccion",
    annotations={
        "title": "Registrar Interacción con Cliente",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def fachmann_registrar_interaccion(params: RegistrarInteraccionInput, ctx: Context) -> str:
    """Guarda una nueva interacción en el historial del cliente: reunión, email, llamada, WhatsApp o nota interna.

    Usar después de cada contacto para mantener el CRM actualizado.
    El cliente_id se obtiene previamente con fachmann_buscar_contexto_cliente.

    Args:
        params (RegistrarInteraccionInput):
            - cliente_id (int): ID numérico del cliente
            - notas (str): Resumen de la interacción, acuerdos tomados y próximos pasos
            - tipo (str): 'reunion', 'email', 'llamada', 'whatsapp' o 'nota' (default: 'nota')

    Returns:
        str: JSON de confirmación:
        {
            "success": true,
            "interaccion_id": int,
            "cliente": str,
            "tipo": str,
            "fecha": str,
            "notas": str
        }
        Retorna error si el cliente_id no existe.

    Examples:
        - Después de una reunión → tipo="reunion", notas="Presentamos propuesta PILZ. Deciden en 2 semanas."
        - Después de un email   → tipo="email",   notas="Enviada cotización formal #COT-2026-042."
        - Nota rápida           → tipo="nota",    notas="LinkedIn: visto que publicó sobre automatización."
    """
    try:
        db: aiosqlite.Connection = ctx.request_context.lifespan_state["db"]

        async with db.execute(
            "SELECT razon_social FROM clientes_prospectos WHERE id = ?",
            (params.cliente_id,),
        ) as cursor:
            cliente_row = await cursor.fetchone()

        if cliente_row is None:
            return (
                f"Error: No existe un cliente con ID {params.cliente_id}. "
                "Use fachmann_buscar_contexto_cliente para obtener el ID correcto."
            )

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with db.execute(
            "INSERT INTO interacciones (cliente_id, tipo, notas, fecha) VALUES (?, ?, ?, ?)",
            (params.cliente_id, params.tipo, params.notas, fecha),
        ) as cursor:
            interaccion_id = cursor.lastrowid

        await db.execute(
            "UPDATE clientes_prospectos SET updated_at = ? WHERE id = ?",
            (fecha, params.cliente_id),
        )
        await db.commit()

        return json.dumps(
            {
                "success": True,
                "interaccion_id": interaccion_id,
                "cliente": dict(cliente_row)["razon_social"],
                "tipo": params.tipo,
                "fecha": fecha,
                "notas": params.notas,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return _db_error(e)


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    mcp.run(transport=transport)
