"""
Cotizador Técnico Fachmann.
Recibe un requerimiento en lenguaje natural y devuelve una propuesta
técnica estructurada usando Claude API con function calling.
"""

import json
import os
import re
from typing import Optional

import anthropic
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# Railway provee postgres://, psycopg2 requiere postgresql://
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = """Sos un experto técnico comercial de Fachmann, representante en Argentina de PILZ, OBO Bettermann y CABUR.

Tu tarea es analizar requerimientos de automatización industrial y seguridad eléctrica, y generar propuestas técnicas precisas.

## Conocimiento normativo que debés aplicar:

### ISO 13849-1:2015 — Seguridad de máquinas
- **PL a**: sin requisitos de arquitectura específica
- **PL b**: Categoría 1 — componente único probado
- **PL c**: Categoría 2 — con test periódico
- **PL d**: Categoría 3 — arquitectura redundante (dos canales)
- **PL e**: Categoría 4 — redundante + detección de fallas comunes

### Reglas de selección PILZ:
- **Parada de emergencia / PL e, Cat 4**: PNOZ s6 (2 canales) o PNOZ XV2
- **Control dos manos / Cat 4**: PNOZ s6 o PNOZ XV2
- **Protección de resguardos / Cat 3–4**: PNOZ XV2
- **Sistemas complejos / múltiples funciones**: PNOZmulti 2 (PNOZ-M-B0)
- **Monitoreo de velocidad segura**: PMCprotego DS
- **Automatización segura a escala**: PSS 4000 CPU

### OBO Bettermann:
- Bandejas portacables: TS 60 E, V-TBS
- Canaletas: WLK
- Cajas de paso: GEK (IP65)

### CABUR:
- Borneras fusibles: XCMF, XCF
- Borneras estándar: XCSF (tornillo), XCT (universal), XCPE (tierra)

## Proceso:
1. Analizá el requerimiento del cliente
2. Usá las herramientas para buscar los productos correctos en el catálogo
3. Verificá disponibilidad y precio exacto con consultar_disponibilidad
4. Generá la propuesta completa

## Formato de respuesta OBLIGATORIO (JSON puro, sin texto adicional):
```json
{
  "cliente": "nombre del cliente o 'No especificado'",
  "requerimiento": "descripción técnica del requerimiento",
  "productos": [
    {
      "sku": "código exacto",
      "descripcion": "descripción completa",
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

El email_draft debe ser profesional, mencionar el cliente por nombre si fue provisto, y resumir la solución técnica propuesta."""

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
                    "enum": ["PILZ", "OBO", "CABUR"],
                    "description": "Filtrar por marca (opcional)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "consultar_disponibilidad",
        "description": "Obtiene precio exacto, stock y tiempo de entrega de un producto por SKU",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "Código exacto del producto (ej. 'PNOZ-S6-24VDC-2NO')"
                }
            },
            "required": ["sku"]
        }
    }
]


def _get_conn():
    return psycopg2.connect(DATABASE_URL)


def _ejecutar_buscar_catalogo(query: str, marca: Optional[str] = None) -> list[dict]:
    like = f"%{query}%"
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if marca:
                cur.execute(
                    """SELECT sku, marca, categoria, descripcion, precio_usd, stock, tiempo_entrega_dias
                       FROM productos_catalogo
                       WHERE activo = 1 AND marca = %s
                         AND (descripcion ILIKE %s OR sku ILIKE %s OR categoria ILIKE %s OR especificaciones ILIKE %s)
                       ORDER BY marca, categoria""",
                    (marca, like, like, like, like),
                )
            else:
                cur.execute(
                    """SELECT sku, marca, categoria, descripcion, precio_usd, stock, tiempo_entrega_dias
                       FROM productos_catalogo
                       WHERE activo = 1
                         AND (descripcion ILIKE %s OR sku ILIKE %s OR categoria ILIKE %s OR especificaciones ILIKE %s)
                       ORDER BY marca, categoria""",
                    (like, like, like, like),
                )
            return [dict(r) for r in cur.fetchall()]


def _ejecutar_consultar_disponibilidad(sku: str) -> dict:
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT sku, marca, categoria, descripcion, precio_usd,
                          especificaciones, stock, tiempo_entrega_dias
                   FROM productos_catalogo WHERE sku = %s AND activo = 1""",
                (sku,),
            )
            row = cur.fetchone()
    if row is None:
        return {"error": f"SKU '{sku}' no encontrado"}
    result = dict(row)
    result["disponible_inmediato"] = result["stock"] > 0
    return result


def _ejecutar_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "buscar_catalogo":
        resultado = _ejecutar_buscar_catalogo(
            query=tool_input["query"],
            marca=tool_input.get("marca"),
        )
        return json.dumps(resultado, ensure_ascii=False)
    elif tool_name == "consultar_disponibilidad":
        resultado = _ejecutar_consultar_disponibilidad(sku=tool_input["sku"])
        return json.dumps(resultado, ensure_ascii=False)
    return json.dumps({"error": f"Tool desconocida: {tool_name}"})


async def llamar_claude(requerimiento: str, cliente: str) -> dict:
    """Llama a Claude API con agentic loop hasta obtener la propuesta completa."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    messages = [
        {
            "role": "user",
            "content": f"Cliente: {cliente or 'No especificado'}\n\nRequerimiento: {requerimiento}"
        }
    ]

    while True:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    resultado = _ejecutar_tool(block.name, block.input)
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
                    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
                    if match:
                        text = match.group(1)
                    elif not text.startswith("{"):
                        start = text.find("{")
                        end = text.rfind("}") + 1
                        if start != -1 and end > start:
                            text = text[start:end]
                    if text:
                        return json.loads(text)

            raise ValueError("Claude no devolvió JSON válido en la respuesta")
        else:
            raise ValueError(f"Stop reason inesperado: {response.stop_reason}")


async def generar_cotizacion(requerimiento: str, cliente: str = "No especificado") -> dict:
    """Punto de entrada principal del cotizador."""
    return await llamar_claude(requerimiento=requerimiento, cliente=cliente)
