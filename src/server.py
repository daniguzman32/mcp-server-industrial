#!/usr/bin/env python3
"""
Servidor MCP para Fachmann — Gestión comercial B2B de automatización industrial.
Marcas representadas: PILZ, OBO Bettermann, CABUR, IDEM Safety.

Herramientas disponibles:
  - fachmann_buscar_catalogo          Busca productos por texto y/o marca
  - fachmann_consultar_disponibilidad Precio, stock y entrega por SKU
  - fachmann_buscar_contexto_cliente  Perfil + historial completo de un cliente
  - fachmann_registrar_interaccion    Guarda reunión / email / llamada en el CRM
  - fachmann_agregar_contacto         Crea un nuevo cliente o prospecto
  - fachmann_actualizar_contacto      Actualiza datos de un contacto existente
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import asyncpg
from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

MARCAS_VALIDAS = {"PILZ", "OBO", "CABUR", "IDEM SAFETY"}
TIPOS_INTERACCION = {"reunion", "email", "llamada", "whatsapp", "nota"}
ESTADOS_LEAD_VALIDOS = {"nuevo_cliente", "calificado", "oferta", "ganado", "cancelado", "perdido"}
ETAPAS_OPORTUNIDAD = {"prospecting", "qualification", "proposal", "negotiation", "closed_won", "closed_lost"}


# ── Lifespan: pool de conexiones a PostgreSQL ─────────────────────────────────

@asynccontextmanager
async def app_lifespan(app):
    pool = await asyncpg.create_pool(DATABASE_URL)
    yield {"db": pool}
    await pool.close()


_port = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
_host = os.getenv("MCP_HOST", "0.0.0.0")

mcp = FastMCP("fachmann_mcp", lifespan=app_lifespan, host=_host, port=_port)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows_to_dicts(rows) -> list[dict]:
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


class AgregarContactoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    razon_social: str = Field(
        ...,
        description="Nombre de la empresa o razón social del contacto",
        min_length=2,
        max_length=200,
    )
    contacto_nombre: Optional[str] = Field(
        default=None,
        description="Nombre y apellido del contacto principal",
        max_length=200,
    )
    contacto_cargo: Optional[str] = Field(
        default=None,
        description="Cargo o puesto del contacto (ej. 'Jefe de Mantenimiento', 'Gerente de Compras')",
        max_length=100,
    )
    contacto_email: Optional[str] = Field(
        default=None,
        description="Email del contacto",
        max_length=200,
    )
    contacto_telefono: Optional[str] = Field(
        default=None,
        description="Teléfono del contacto",
        max_length=50,
    )
    industria: Optional[str] = Field(
        default=None,
        description="Sector o industria (ej. 'Automotriz', 'Alimentos', 'Oil & Gas')",
        max_length=100,
    )
    estado_lead: str = Field(
        default="nuevo_cliente",
        description="Estado del lead: 'nuevo_cliente', 'calificado', 'oferta', 'ganado', 'cancelado', 'perdido'",
    )
    linkedin_url: Optional[str] = Field(
        default=None,
        description="URL del perfil LinkedIn de la empresa o contacto",
        max_length=300,
    )
    notas: Optional[str] = Field(
        default=None,
        description="Notas internas sobre el contacto o empresa",
        max_length=2000,
    )

    @field_validator("estado_lead")
    @classmethod
    def validate_estado_lead(cls, v: str) -> str:
        v_lower = v.strip().lower()
        if v_lower not in ESTADOS_LEAD_VALIDOS:
            raise ValueError(f"Estado inválido '{v}'. Opciones: {', '.join(sorted(ESTADOS_LEAD_VALIDOS))}.")
        return v_lower


class GestionarOportunidadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    oportunidad_id: Optional[int] = Field(
        default=None,
        description="ID de la oportunidad a actualizar. Omitir para crear una nueva.",
        ge=1,
    )
    cliente_id: Optional[int] = Field(
        default=None,
        description="ID del cliente (requerido al crear). Obtener con fachmann_buscar_contexto_cliente.",
        ge=1,
    )
    descripcion: Optional[str] = Field(
        default=None,
        description="Descripción del proyecto u oportunidad",
        min_length=3,
        max_length=500,
    )
    monto_usd: Optional[float] = Field(
        default=None,
        description="Valor estimado de la oportunidad en USD",
        ge=0,
    )
    probabilidad_cierre: Optional[int] = Field(
        default=None,
        description="Probabilidad de cierre en porcentaje (0–100)",
        ge=0,
        le=100,
    )
    etapa: Optional[str] = Field(
        default=None,
        description="Etapa: 'prospecting', 'qualification', 'proposal', 'negotiation', 'closed_won', 'closed_lost'",
    )
    notas_tecnicas: Optional[str] = Field(
        default=None,
        description="Notas técnicas o comerciales de la oportunidad",
        max_length=2000,
    )
    fecha_cierre_estimada: Optional[str] = Field(
        default=None,
        description="Fecha estimada de cierre (formato YYYY-MM-DD)",
        max_length=10,
    )

    @field_validator("etapa")
    @classmethod
    def validate_etapa(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_lower = v.strip().lower()
        if v_lower not in ETAPAS_OPORTUNIDAD:
            raise ValueError(f"Etapa inválida '{v}'. Opciones: {', '.join(sorted(ETAPAS_OPORTUNIDAD))}.")
        return v_lower


class ActualizarContactoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    cliente_id: int = Field(
        ...,
        description="ID numérico del cliente a actualizar. Obtenerlo con fachmann_buscar_contexto_cliente.",
        ge=1,
    )
    razon_social: Optional[str] = Field(
        default=None,
        description="Nuevo nombre de la empresa o razón social",
        min_length=2,
        max_length=200,
    )
    contacto_nombre: Optional[str] = Field(
        default=None,
        description="Nombre y apellido del contacto principal",
        max_length=200,
    )
    contacto_cargo: Optional[str] = Field(
        default=None,
        description="Cargo o puesto del contacto",
        max_length=100,
    )
    contacto_email: Optional[str] = Field(
        default=None,
        description="Email del contacto",
        max_length=200,
    )
    contacto_telefono: Optional[str] = Field(
        default=None,
        description="Teléfono del contacto",
        max_length=50,
    )
    industria: Optional[str] = Field(
        default=None,
        description="Sector o industria",
        max_length=100,
    )
    estado_lead: Optional[str] = Field(
        default=None,
        description="Estado del lead: 'nuevo_cliente', 'calificado', 'oferta', 'ganado', 'cancelado', 'perdido'",
    )
    linkedin_url: Optional[str] = Field(
        default=None,
        description="URL del perfil LinkedIn",
        max_length=300,
    )
    notas: Optional[str] = Field(
        default=None,
        description="Notas internas (reemplaza las existentes)",
        max_length=2000,
    )

    @field_validator("estado_lead")
    @classmethod
    def validate_estado_lead(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_lower = v.strip().lower()
        if v_lower not in ESTADOS_LEAD_VALIDOS:
            raise ValueError(f"Estado inválido '{v}'. Opciones: {', '.join(sorted(ESTADOS_LEAD_VALIDOS))}.")
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
        str: JSON con lista de productos encontrados.
    """
    try:
        pool: asyncpg.Pool = ctx.request_context.lifespan_state["db"]
        like = f"%{params.query}%"

        async with pool.acquire() as conn:
            if params.marca:
                rows = await conn.fetch(
                    """SELECT sku, marca, categoria, descripcion, precio_usd, stock, tiempo_entrega_dias
                       FROM productos_catalogo
                       WHERE activo = 1 AND marca = $1
                         AND (descripcion ILIKE $2 OR sku ILIKE $3 OR categoria ILIKE $4 OR especificaciones ILIKE $5)
                       ORDER BY marca, categoria, sku""",
                    params.marca, like, like, like, like,
                )
            else:
                rows = await conn.fetch(
                    """SELECT sku, marca, categoria, descripcion, precio_usd, stock, tiempo_entrega_dias
                       FROM productos_catalogo
                       WHERE activo = 1
                         AND (descripcion ILIKE $1 OR sku ILIKE $2 OR categoria ILIKE $3 OR especificaciones ILIKE $4)
                       ORDER BY marca, categoria, sku""",
                    like, like, like, like,
                )

        rows = _rows_to_dicts(rows)

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
        str: JSON con ficha completa del producto.
    """
    try:
        pool: asyncpg.Pool = ctx.request_context.lifespan_state["db"]

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT sku, marca, categoria, descripcion, precio_usd,
                          especificaciones, stock, tiempo_entrega_dias
                   FROM productos_catalogo
                   WHERE sku = $1 AND activo = 1""",
                params.sku,
            )

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
        str: JSON con coincidencias encontradas, incluyendo historial e interacciones.
    """
    try:
        pool: asyncpg.Pool = ctx.request_context.lifespan_state["db"]
        like = f"%{params.empresa}%"

        async with pool.acquire() as conn:
            clientes_rows = await conn.fetch(
                """SELECT id, razon_social, contacto_nombre, contacto_cargo, contacto_email,
                          contacto_telefono, industria, estado_lead, linkedin_url, notas, created_at
                   FROM clientes_prospectos
                   WHERE razon_social ILIKE $1 OR contacto_nombre ILIKE $2
                   ORDER BY razon_social""",
                like, like,
            )

            if not clientes_rows:
                return f"No se encontraron clientes que coincidan con '{params.empresa}'."

            clientes = _rows_to_dicts(clientes_rows)

            for cliente in clientes:
                cid = cliente["id"]

                cliente["interacciones_recientes"] = _rows_to_dicts(await conn.fetch(
                    """SELECT tipo, notas, fecha FROM interacciones
                       WHERE cliente_id = $1
                       ORDER BY fecha DESC LIMIT 5""",
                    cid,
                ))

                cliente["oportunidades_activas"] = _rows_to_dicts(await conn.fetch(
                    """SELECT id, descripcion, monto_usd, probabilidad_cierre, etapa, notas_tecnicas, fecha_cierre_estimada
                       FROM oportunidades_ventas
                       WHERE cliente_id = $1 AND etapa NOT IN ('closed_won', 'closed_lost')
                       ORDER BY probabilidad_cierre DESC""",
                    cid,
                ))

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
        str: JSON de confirmación con interaccion_id, cliente, tipo y fecha.
    """
    try:
        pool: asyncpg.Pool = ctx.request_context.lifespan_state["db"]
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with pool.acquire() as conn:
            cliente_row = await conn.fetchrow(
                "SELECT razon_social FROM clientes_prospectos WHERE id = $1",
                params.cliente_id,
            )

            if cliente_row is None:
                return (
                    f"Error: No existe un cliente con ID {params.cliente_id}. "
                    "Use fachmann_buscar_contexto_cliente para obtener el ID correcto."
                )

            async with conn.transaction():
                interaccion_id = await conn.fetchval(
                    "INSERT INTO interacciones (cliente_id, tipo, notas, fecha) VALUES ($1, $2, $3, $4) RETURNING id",
                    params.cliente_id, params.tipo, params.notas, fecha,
                )
                await conn.execute(
                    "UPDATE clientes_prospectos SET updated_at = $1 WHERE id = $2",
                    fecha, params.cliente_id,
                )

        return json.dumps(
            {
                "success": True,
                "interaccion_id": interaccion_id,
                "cliente": cliente_row["razon_social"],
                "tipo": params.tipo,
                "fecha": fecha,
                "notas": params.notas,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return _db_error(e)


@mcp.tool(
    name="fachmann_agregar_contacto",
    annotations={
        "title": "Agregar Nuevo Contacto o Empresa al CRM",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def fachmann_agregar_contacto(params: AgregarContactoInput, ctx: Context) -> str:
    """Crea un nuevo cliente o prospecto en el CRM de Fachmann.

    Usar cuando se identifica un nuevo lead o se establece primer contacto con una empresa.
    Si el contacto ya existe, usar fachmann_actualizar_contacto en su lugar.

    Args:
        params (AgregarContactoInput):
            - razon_social (str): Nombre de la empresa (requerido)
            - contacto_nombre (Optional[str]): Nombre del contacto principal
            - contacto_cargo (Optional[str]): Cargo del contacto
            - contacto_email (Optional[str]): Email
            - contacto_telefono (Optional[str]): Teléfono
            - industria (Optional[str]): Sector (ej. 'Automotriz', 'Alimentos')
            - estado_lead (str): Estado del lead (default: 'nuevo_cliente')
            - linkedin_url (Optional[str]): URL LinkedIn
            - notas (Optional[str]): Notas internas

    Returns:
        str: JSON de confirmación con el cliente_id asignado.
    """
    try:
        pool: asyncpg.Pool = ctx.request_context.lifespan_state["db"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with pool.acquire() as conn:
            cliente_id = await conn.fetchval(
                """INSERT INTO clientes_prospectos
                   (razon_social, contacto_nombre, contacto_cargo, contacto_email,
                    contacto_telefono, industria, estado_lead, linkedin_url, notas,
                    created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                   RETURNING id""",
                params.razon_social,
                params.contacto_nombre,
                params.contacto_cargo,
                params.contacto_email,
                params.contacto_telefono,
                params.industria,
                params.estado_lead,
                params.linkedin_url,
                params.notas,
                now,
                now,
            )

        return json.dumps(
            {
                "success": True,
                "cliente_id": cliente_id,
                "razon_social": params.razon_social,
                "estado_lead": params.estado_lead,
                "mensaje": f"Contacto '{params.razon_social}' creado con ID {cliente_id}.",
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return _db_error(e)


@mcp.tool(
    name="fachmann_actualizar_contacto",
    annotations={
        "title": "Actualizar Datos de un Contacto Existente",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def fachmann_actualizar_contacto(params: ActualizarContactoInput, ctx: Context) -> str:
    """Actualiza uno o más campos de un cliente o prospecto existente en el CRM.

    Solo actualiza los campos que se provean — los campos omitidos no se modifican.
    El cliente_id se obtiene previamente con fachmann_buscar_contexto_cliente.

    Args:
        params (ActualizarContactoInput):
            - cliente_id (int): ID del cliente a actualizar (requerido)
            - razon_social / contacto_nombre / contacto_cargo / contacto_email /
              contacto_telefono / industria / estado_lead / linkedin_url / notas:
              Todos opcionales. Solo se actualizan los que se pasen.

    Returns:
        str: JSON de confirmación con los campos actualizados.
    """
    try:
        pool: asyncpg.Pool = ctx.request_context.lifespan_state["db"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        campos = {
            "razon_social": params.razon_social,
            "contacto_nombre": params.contacto_nombre,
            "contacto_cargo": params.contacto_cargo,
            "contacto_email": params.contacto_email,
            "contacto_telefono": params.contacto_telefono,
            "industria": params.industria,
            "estado_lead": params.estado_lead,
            "linkedin_url": params.linkedin_url,
            "notas": params.notas,
        }
        actualizados = {k: v for k, v in campos.items() if v is not None}

        if not actualizados:
            return "Error: Debe proveer al menos un campo para actualizar."

        async with pool.acquire() as conn:
            cliente_row = await conn.fetchrow(
                "SELECT razon_social FROM clientes_prospectos WHERE id = $1",
                params.cliente_id,
            )
            if cliente_row is None:
                return (
                    f"Error: No existe un cliente con ID {params.cliente_id}. "
                    "Use fachmann_buscar_contexto_cliente para obtener el ID correcto."
                )

            set_parts = [f"{col} = ${i + 1}" for i, col in enumerate(actualizados)]
            set_parts.append(f"updated_at = ${len(actualizados) + 1}")
            valores = list(actualizados.values()) + [now, params.cliente_id]

            await conn.execute(
                f"UPDATE clientes_prospectos SET {', '.join(set_parts)} WHERE id = ${len(valores)}",
                *valores,
            )

        return json.dumps(
            {
                "success": True,
                "cliente_id": params.cliente_id,
                "razon_social": cliente_row["razon_social"],
                "campos_actualizados": list(actualizados.keys()),
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return _db_error(e)


@mcp.tool(
    name="fachmann_gestionar_oportunidad",
    annotations={
        "title": "Crear o Actualizar Oportunidad de Venta",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def fachmann_gestionar_oportunidad(params: GestionarOportunidadInput, ctx: Context) -> str:
    """Crea una nueva oportunidad de venta o actualiza una existente en el pipeline.

    Para crear: omitir oportunidad_id y proveer cliente_id + descripcion.
    Para actualizar: proveer oportunidad_id y los campos a cambiar.

    Etapas disponibles: prospecting → qualification → proposal → negotiation → closed_won / closed_lost.

    Args:
        params (GestionarOportunidadInput):
            - oportunidad_id (Optional[int]): ID a actualizar, o None para crear
            - cliente_id (Optional[int]): Requerido al crear
            - descripcion, monto_usd, probabilidad_cierre, etapa, notas_tecnicas, fecha_cierre_estimada

    Returns:
        str: JSON de confirmación con el oportunidad_id.
    """
    try:
        pool: asyncpg.Pool = ctx.request_context.lifespan_state["db"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with pool.acquire() as conn:
            # ── Crear ──────────────────────────────────────────────────────────
            if params.oportunidad_id is None:
                if not params.cliente_id or not params.descripcion:
                    return "Error: Para crear una oportunidad se requieren cliente_id y descripcion."

                cliente_row = await conn.fetchrow(
                    "SELECT razon_social FROM clientes_prospectos WHERE id = $1",
                    params.cliente_id,
                )
                if cliente_row is None:
                    return f"Error: No existe cliente con ID {params.cliente_id}."

                oportunidad_id = await conn.fetchval(
                    """INSERT INTO oportunidades_ventas
                       (cliente_id, descripcion, monto_usd, probabilidad_cierre,
                        etapa, notas_tecnicas, fecha_cierre_estimada, fecha_creacion, updated_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                       RETURNING id""",
                    params.cliente_id,
                    params.descripcion,
                    params.monto_usd,
                    params.probabilidad_cierre or 25,
                    params.etapa or "prospecting",
                    params.notas_tecnicas,
                    params.fecha_cierre_estimada,
                    now, now,
                )
                return json.dumps(
                    {
                        "success": True,
                        "accion": "creada",
                        "oportunidad_id": oportunidad_id,
                        "cliente": cliente_row["razon_social"],
                        "descripcion": params.descripcion,
                        "etapa": params.etapa or "prospecting",
                    },
                    indent=2, ensure_ascii=False,
                )

            # ── Actualizar ─────────────────────────────────────────────────────
            op_row = await conn.fetchrow(
                """SELECT o.id, c.razon_social FROM oportunidades_ventas o
                   JOIN clientes_prospectos c ON c.id = o.cliente_id
                   WHERE o.id = $1""",
                params.oportunidad_id,
            )
            if op_row is None:
                return f"Error: No existe oportunidad con ID {params.oportunidad_id}."

            campos = {
                "descripcion": params.descripcion,
                "monto_usd": params.monto_usd,
                "probabilidad_cierre": params.probabilidad_cierre,
                "etapa": params.etapa,
                "notas_tecnicas": params.notas_tecnicas,
                "fecha_cierre_estimada": params.fecha_cierre_estimada,
            }
            actualizados = {k: v for k, v in campos.items() if v is not None}

            if not actualizados:
                return "Error: Debe proveer al menos un campo para actualizar."

            set_parts = [f"{col} = ${i + 1}" for i, col in enumerate(actualizados)]
            set_parts.append(f"updated_at = ${len(actualizados) + 1}")
            valores = list(actualizados.values()) + [now, params.oportunidad_id]

            await conn.execute(
                f"UPDATE oportunidades_ventas SET {', '.join(set_parts)} WHERE id = ${len(valores)}",
                *valores,
            )

            return json.dumps(
                {
                    "success": True,
                    "accion": "actualizada",
                    "oportunidad_id": params.oportunidad_id,
                    "cliente": op_row["razon_social"],
                    "campos_actualizados": list(actualizados.keys()),
                },
                indent=2, ensure_ascii=False,
            )

    except Exception as e:
        return _db_error(e)


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    mcp.run(transport=transport)
