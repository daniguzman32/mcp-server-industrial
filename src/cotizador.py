"""
Cotizador Técnico Fachmann.
Recibe un requerimiento en lenguaje natural y devuelve una propuesta
técnica estructurada usando Claude API con function calling.
"""

import json
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)

import anthropic
import asyncpg
from dotenv import load_dotenv

load_dotenv()

# Railway provee postgres://, psycopg2 requiere postgresql://
_raw_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL", "")
DATABASE_URL = _raw_url.replace("postgres://", "postgresql://", 1)
if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT_BASE = """Sos un experto técnico comercial de Fachmann, representante en Argentina de PILZ, OBO Bettermann, CABUR e IDEM Safety.

Tu tarea es analizar requerimientos de automatización industrial y seguridad eléctrica, y generar propuestas técnicas precisas basadas exclusivamente en el catálogo real de Fachmann.

## Regla fundamental — sin excepciones:
NUNCA incluyas un producto en la propuesta si no fue devuelto por la herramienta `buscar_catalogo` y confirmado con `consultar_disponibilidad`. Todos los SKUs y precios de la propuesta deben provenir de las herramientas. No inventes ni asumas SKUs, descripciones ni precios.

Si `consultar_disponibilidad` devuelve `{"error": "SKU '...' no encontrado"}`, ese producto NO existe en nuestro catálogo — no lo incluyas y buscá una alternativa con `buscar_catalogo`.

## Proceso obligatorio:
1. Si falta información crítica para hacer una buena selección técnica, devolvé el formato "preguntas" (ver más abajo) para pedirla antes de generar la propuesta.
2. Buscá los productos con `buscar_catalogo` usando términos descriptivos (aplicación, tipo de producto, categoría de seguridad, tensión).
3. Confirmá cada producto candidato con `consultar_disponibilidad` — ese es el único precio válido.
4. Si un SKU da error en `consultar_disponibilidad`, descartalo y buscá otra opción.
5. Generá la propuesta solo con productos confirmados.

## Cuándo pedir información antes de cotizar:
Pedí aclaraciones si el requerimiento no tiene suficiente detalle para seleccionar el producto correcto. Preguntas útiles según el contexto:
- ¿Para qué cliente es? (para personalizar el email)
- ¿Cuántas unidades necesitás?
- ¿Cuál es la tensión de trabajo? (24 VDC / 110 VAC / 230 VAC)
- ¿Cuál es el nivel de performance requerido? (PL c, PL d, PL e / SIL 1, SIL 2, SIL 3)
- ¿Cuántas funciones de seguridad simultáneas necesitás?
- ¿Es para un tablero nuevo o expansión de uno existente?

No preguntes por información que ya está en el requerimiento. Máximo 3 preguntas por ronda.

## Conocimiento normativo de referencia (para buscar, no para asumir SKUs):

### ISO 13849-1:2015 — Seguridad de máquinas
- **PL a**: sin requisitos de arquitectura específica
- **PL b**: Categoría 1 — componente único probado
- **PL c**: Categoría 2 — con test periódico
- **PL d**: Categoría 3 — arquitectura redundante (dos canales)
- **PL e**: Categoría 4 — redundante + detección de fallas comunes

Términos de búsqueda útiles en el catálogo:
- Relés de seguridad PILZ: buscá "relé seguridad", "parada emergencia", "control dos manos", "monitor velocidad"
- Bandejas y canaletas OBO: buscá "bandeja portacables", "canaleta", "caja paso"
- Borneras CABUR: buscá "bornera fusible", "bornera estándar", "borne tierra"
- Dispositivos IDEM Safety: buscá "interruptor seguridad", "sensor puerta", "final carrera seguridad"

## Formatos de respuesta OBLIGATORIOS (JSON puro, sin texto adicional):

### Cuando falta información — devolvé este formato:
```json
{
  "tipo": "preguntas",
  "resumen_requerimiento": "lo que entendiste del requerimiento hasta ahora",
  "preguntas": [
    "¿Pregunta 1?",
    "¿Pregunta 2?"
  ]
}
```

### Cuando tenés todo — devolvé la propuesta:
```json
{
  "tipo": "propuesta",
  "cliente": "nombre del cliente o 'No especificado'",
  "requerimiento": "descripción técnica del requerimiento",
  "productos": [
    {
      "sku": "código exacto obtenido de buscar_catalogo",
      "descripcion": "descripción completa del catálogo",
      "cantidad": 1,
      "precio_usd": 320.0,
      "justificacion": "por qué este producto para este requerimiento"
    }
  ],
  "norma_aplicable": "ISO/IEC aplicable con PL y categoría",
  "total_usd": 320.0,
  "validez_dias": 30,
  "tiempo_entrega_dias": 21,
  "notas_tecnicas": "observaciones adicionales si aplica",
  "email_draft": "borrador completo del email al cliente"
}
```

El `precio_usd` de cada producto debe ser el `precio_neto_usd` devuelto por `consultar_disponibilidad` (con descuento si hay tarifa activa).
El `total_usd` es la suma de `cantidad × precio_usd` de cada item.
El `email_draft` debe ser profesional, mencionar el cliente por nombre si fue provisto, y resumir la solución técnica propuesta.

## Reglas de stock y entrega

Al llamar a `consultar_disponibilidad`, siempre pasá la cantidad requerida en el campo `cantidad`.
La función devuelve `estado_stock` con tres valores posibles:

- **"disponible"**: hay stock suficiente. `tiempo_entrega_estimado_dias = 0`.
- **"sin_stock"**: no hay unidades. `tiempo_entrega_estimado_dias = 28`. En `notas_tecnicas` indicá "Producto bajo pedido, entrega estimada 4 semanas."
- **"parcial"**: hay stock pero insuficiente. `tiempo_entrega_estimado_dias = 28`. En `notas_tecnicas` indicá cuántas unidades son inmediatas y cuántas bajo pedido.

El campo `tiempo_entrega_dias` de la propuesta debe reflejar el plazo más largo entre todos los productos.
Si algún producto es parcial o sin stock, mencionalo en el `email_draft` con lenguaje profesional."""

TOOLS = [
    {
        "name": "buscar_catalogo",
        "description": "Busca productos en el catálogo de Fachmann por texto libre y marca opcional",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar (ej. 'relé seguridad', 'bandeja', 'bornera')"
                },
                "marca": {
                    "type": "string",
                    "enum": ["PILZ", "OBO", "CABUR", "IDEM SAFETY"],
                    "description": "Filtrar por marca (opcional)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "consultar_disponibilidad",
        "description": "Obtiene precio de lista, precio neto con descuento aplicado según tarifa, stock y tiempo de entrega de un producto por SKU. Siempre pasar la cantidad requerida para calcular si hay stock suficiente o entrega parcial.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "Código exacto del producto (ej. 'PNOZ-S6-24VDC-2NO')"
                },
                "cantidad": {
                    "type": "integer",
                    "description": "Cantidad requerida por el cliente. Default 1.",
                    "minimum": 1,
                    "default": 1
                }
            },
            "required": ["sku"]
        }
    },
    {
        "name": "listar_tarifas",
        "description": "Lista las tarifas de descuento disponibles con sus porcentajes por marca",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


@asynccontextmanager
async def _get_conn():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()


def _aplicar_descuento(precio_lista: float, d1: float, d2: float, d3: float) -> float:
    """Descuentos en cascada: precio * (1-d1/100) * (1-d2/100) * (1-d3/100)"""
    return round(precio_lista * (1 - d1/100) * (1 - d2/100) * (1 - d3/100), 4)


async def _cargar_regla_tarifa(tarifa_nombre: str, marca: str) -> Optional[dict]:
    """Retorna la regla de descuento para tarifa+marca, o None si no existe."""
    async with _get_conn() as conn:
        row = await conn.fetchrow(
            """SELECT desc_1, desc_2, desc_3
               FROM reglas_descuento
               WHERE tarifa_nombre = $1 AND marca = $2""",
            tarifa_nombre, marca,
        )
    return dict(row) if row else None


async def _ejecutar_listar_tarifas() -> list[dict]:
    async with _get_conn() as conn:
        rows = [dict(r) for r in await conn.fetch(
            """SELECT tarifa_nombre, marca, desc_1, desc_2, desc_3
               FROM reglas_descuento
               ORDER BY tarifa_nombre, marca"""
        )]
    # Agrupar por tarifa para presentación legible
    tarifas: dict = {}
    for r in rows:
        t = r["tarifa_nombre"]
        if t not in tarifas:
            tarifas[t] = {"tarifa_nombre": t, "descuentos_por_marca": {}}
        tarifas[t]["descuentos_por_marca"][r["marca"]] = {
            "desc_1": r["desc_1"],
            "desc_2": r["desc_2"],
            "desc_3": r["desc_3"],
        }
    return list(tarifas.values())


_BUSCAR_LIMIT = 20


async def _ejecutar_buscar_catalogo(query: str, marca: Optional[str] = None) -> dict:
    like = f"%{query}%"
    async with _get_conn() as conn:
        if marca:
            rows = [dict(r) for r in await conn.fetch(
                """SELECT sku, marca, categoria, descripcion,
                          precio_usd AS precio_lista_usd, stock, tiempo_entrega_dias
                   FROM productos_catalogo
                   WHERE activo = 1 AND marca = $1
                     AND (descripcion ILIKE $2 OR sku ILIKE $3 OR categoria ILIKE $4 OR especificaciones ILIKE $5)
                   ORDER BY marca, categoria
                   LIMIT $6""",
                marca, like, like, like, like, _BUSCAR_LIMIT,
            )]
        else:
            rows = [dict(r) for r in await conn.fetch(
                """SELECT sku, marca, categoria, descripcion,
                          precio_usd AS precio_lista_usd, stock, tiempo_entrega_dias
                   FROM productos_catalogo
                   WHERE activo = 1
                     AND (descripcion ILIKE $1 OR sku ILIKE $2 OR categoria ILIKE $3 OR especificaciones ILIKE $4)
                   ORDER BY marca, categoria
                   LIMIT $5""",
                like, like, like, like, _BUSCAR_LIMIT,
            )]

    return {
        "total_mostrados": len(rows),
        "nota": f"Se muestran hasta {_BUSCAR_LIMIT} resultados. Refiná la búsqueda si no encontrás el producto.",
        "productos": rows,
    }


_LEAD_TIME_SIN_STOCK_DIAS = 28  # 4 semanas para productos bajo pedido


async def _ejecutar_consultar_disponibilidad(
    sku: str,
    tarifa_nombre: Optional[str] = None,
    cantidad: int = 1,
) -> dict:
    async with _get_conn() as conn:
        row = await conn.fetchrow(
            """SELECT sku, marca, categoria, descripcion, precio_usd,
                      especificaciones, stock, tiempo_entrega_dias
               FROM productos_catalogo WHERE sku = $1 AND activo = 1""",
            sku,
        )
    if row is None:
        return {"error": f"SKU '{sku}' no encontrado"}
    result = dict(row)
    result["precio_lista_usd"] = result["precio_usd"]

    # ── Análisis de stock vs cantidad solicitada ──────────────────────────────
    stock = result["stock"]
    result["cantidad_solicitada"] = cantidad
    result["unidades_disponibles"] = stock
    result["unidades_bajo_pedido"] = max(0, cantidad - stock)

    if stock >= cantidad:
        result["estado_stock"] = "disponible"
        result["tiempo_entrega_estimado_dias"] = 0
        result["nota_entrega"] = f"Stock suficiente ({stock} unidades disponibles)."
    elif stock == 0:
        result["estado_stock"] = "sin_stock"
        result["tiempo_entrega_estimado_dias"] = _LEAD_TIME_SIN_STOCK_DIAS
        result["nota_entrega"] = f"Sin stock. Entrega en {_LEAD_TIME_SIN_STOCK_DIAS} días (bajo pedido)."
    else:
        result["estado_stock"] = "parcial"
        result["tiempo_entrega_estimado_dias"] = _LEAD_TIME_SIN_STOCK_DIAS
        result["nota_entrega"] = (
            f"Stock parcial: {stock} unidades disponibles de inmediato, "
            f"{cantidad - stock} unidades bajo pedido ({_LEAD_TIME_SIN_STOCK_DIAS} días)."
        )

    # ── Precio con tarifa ─────────────────────────────────────────────────────
    if tarifa_nombre:
        regla = await _cargar_regla_tarifa(tarifa_nombre, result["marca"])
        if regla:
            precio_neto = _aplicar_descuento(
                result["precio_usd"], regla["desc_1"], regla["desc_2"], regla["desc_3"]
            )
            desc_efectivo = round(100 * (1 - precio_neto / result["precio_usd"]), 2) if result["precio_usd"] else 0
            result["tarifa_aplicada"] = tarifa_nombre
            result["descuento_efectivo_pct"] = desc_efectivo
            result["precio_neto_usd"] = precio_neto
        else:
            result["tarifa_aplicada"] = None
            result["precio_neto_usd"] = result["precio_usd"]
            result["nota_tarifa"] = f"Tarifa '{tarifa_nombre}' no encontrada para marca {result['marca']}. Se usa precio de lista."
    else:
        result["precio_neto_usd"] = result["precio_usd"]

    return result


async def _ejecutar_tool(tool_name: str, tool_input: dict, tarifa_nombre: Optional[str] = None) -> str:
    if tool_name == "buscar_catalogo":
        resultado = await _ejecutar_buscar_catalogo(
            query=tool_input["query"],
            marca=tool_input.get("marca"),
        )
        return json.dumps(resultado, ensure_ascii=False)
    elif tool_name == "consultar_disponibilidad":
        resultado = await _ejecutar_consultar_disponibilidad(
            sku=tool_input["sku"],
            tarifa_nombre=tarifa_nombre,
            cantidad=tool_input.get("cantidad", 1),
        )
        return json.dumps(resultado, ensure_ascii=False)
    elif tool_name == "listar_tarifas":
        resultado = await _ejecutar_listar_tarifas()
        return json.dumps(resultado, ensure_ascii=False)
    return json.dumps({"error": f"Tool desconocida: {tool_name}"})


def _build_system_prompt(tarifa_nombre: Optional[str]) -> str:
    if tarifa_nombre:
        tarifa_info = (
            f"\n\n## Tarifa activa: {tarifa_nombre}\n"
            "Al llamar a consultar_disponibilidad, el sistema aplica automáticamente los descuentos de esta tarifa.\n"
            "El campo `precio_neto_usd` es el precio final al cliente. Usá ese valor en la propuesta."
        )
    else:
        tarifa_info = (
            "\n\n## Tarifa: sin descuento aplicado\n"
            "Los precios son de lista (sin descuento). Podés llamar a listar_tarifas para ver las opciones disponibles."
        )
    return SYSTEM_PROMPT_BASE + tarifa_info


_MAX_ITER = 10


async def llamar_claude(requerimiento: str, cliente: str, tarifa_nombre: Optional[str]) -> dict:
    """Llama a Claude API con agentic loop hasta obtener la propuesta completa."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    messages = [
        {
            "role": "user",
            "content": f"Cliente: {cliente or 'No especificado'}\n\nRequerimiento: {requerimiento}"
        }
    ]

    for _iter in range(_MAX_ITER):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            system=_build_system_prompt(tarifa_nombre),
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    resultado = await _ejecutar_tool(block.name, block.input, tarifa_nombre)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": resultado,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    text = block.text.strip()
                    logger.info("Respuesta Claude (iter %d): %s", _iter, text[:500])

                    # Intento 1: JSON limpio directo
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        pass

                    # Intento 2: extraer del fence ```json ... ```
                    fence = re.search(r"```(?:json)?\s*(\{.*?)\s*```", text, re.DOTALL)
                    if fence:
                        try:
                            return json.loads(fence.group(1))
                        except json.JSONDecodeError:
                            pass

                    # Intento 3: raw_decode desde el primer {
                    start = text.find("{")
                    if start != -1:
                        try:
                            obj, _ = json.JSONDecoder().raw_decode(text, start)
                            return obj
                        except json.JSONDecodeError:
                            pass

                    logger.error("No se pudo parsear JSON del bloque:\n%s", text)

            raise ValueError("Claude no devolvió JSON válido en la respuesta")
        else:
            raise ValueError(f"Stop reason inesperado: {response.stop_reason}")

    raise ValueError(f"El agentic loop superó el máximo de {_MAX_ITER} iteraciones sin devolver respuesta")


async def generar_cotizacion(
    requerimiento: str,
    cliente: str = "No especificado",
    tarifa_nombre: Optional[str] = None,
) -> dict:
    """Punto de entrada principal del cotizador.

    Args:
        requerimiento: Descripción del requerimiento técnico en lenguaje natural.
            Puede incluir respuestas a preguntas previas concatenadas al requerimiento original.
        cliente: Nombre del cliente o empresa.
        tarifa_nombre: Nombre exacto de la tarifa en reglas_descuento. Si es None, usa precio de lista.

    Returns:
        dict con "tipo": "propuesta" o "tipo": "preguntas".
    """
    return await llamar_claude(
        requerimiento=requerimiento,
        cliente=cliente,
        tarifa_nombre=tarifa_nombre,
    )
