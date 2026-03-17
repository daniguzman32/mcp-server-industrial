"""
Telegram bot para el Cotizador Técnico Fachmann.
Recibe requerimientos en lenguaje natural y devuelve propuesta PDF + email draft.
"""

import asyncio
import logging
import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from src.cotizador import (
    CLAUDE_MODEL_PROPUESTA,
    buscar_cliente,
    generar_cotizacion,
    registrar_interaccion,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

_TTL_SEGUNDOS = 1800        # 30 min — expiración de estado wizard
_COTIZACION_TIMEOUT = 120   # segundos — timeout de llamadas al cotizador

# Rate limiting: máx 5 mensajes por usuario en 10 segundos
_RATE_LIMIT_CALLS = 5
_RATE_LIMIT_WINDOW = 10
_user_timestamps: dict[int, list[float]] = defaultdict(list)

# Palabras que indican que el usuario quiere modificar la propuesta anterior
_PALABRAS_REFINAMIENTO = frozenset([
    "modific", "cambi", "agrega", "quit", "reemplaz",
    "mismo cliente", "anterior", "más unidades", "menos unidades",
    "actualiz", "aumentar", "reducir", "otra opción", "alternativa",
])

# Saludos y entradas triviales que no ameritan llamar al LLM
_SALUDOS = frozenset([
    "hola", "hi", "hey", "buenas", "buen dia", "buen día",
    "buenos dias", "buenos días", "ok", "gracias", "si", "sí",
    "no", "dale", "listo", "perfecto", "genial", "excelente",
])

# Patrones para extraer el nombre del cliente del texto libre
_RE_CLIENTE = [
    re.compile(r'cliente[:\s]+([A-Za-záéíóúñÁÉÍÓÚÑ][^\s,\.\n]{1,}(?:\s[A-Za-záéíóúñÁÉÍÓÚÑ][^\s,\.\n]{1,}){0,2})', re.IGNORECASE),
    re.compile(r'para\s+(?:la\s+empresa\s+|el\s+cliente\s+)?([A-Z][^\s,\.\n]{1,}(?:\s[A-Z][^\s,\.\n]{1,}){0,2})'),
    re.compile(r'empresa[:\s]+([A-Za-záéíóúñÁÉÍÓÚÑ][^\s,\.\n]{1,}(?:\s[A-Za-záéíóúñÁÉÍÓÚÑ][^\s,\.\n]{1,}){0,2})', re.IGNORECASE),
]


# ── Helpers de análisis de input ──────────────────────────────────────────────

def _extraer_cliente(texto: str) -> str:
    for pattern in _RE_CLIENTE:
        m = pattern.search(texto)
        if m:
            return m.group(1).strip().rstrip('.,;: ')
    return "No especificado"


def _es_input_trivial(texto: str) -> bool:
    limpio = texto.lower().strip().rstrip('!?.¿¡')
    return limpio in _SALUDOS or len(texto) < 5


def _es_refinamiento(texto: str, ultima_propuesta: dict | None) -> bool:
    if not ultima_propuesta:
        return False
    texto_lower = texto.lower()
    return any(p in texto_lower for p in _PALABRAS_REFINAMIENTO)


def _resumen_propuesta(propuesta: dict) -> str:
    """Texto compacto de una propuesta para contexto multi-turno."""
    cliente = propuesta.get("cliente", "cliente desconocido")
    items = ", ".join(
        f"{p['sku']} x{p['cantidad']}"
        for p in propuesta.get("productos", [])[:5]
    )
    total = propuesta.get("total_usd", 0)
    return f"PROPUESTA ANTERIOR — Cliente: {cliente} | Productos: {items} | Total: USD {total:.2f}"


def _estado_expirado(ctx: dict) -> bool:
    return time.time() - ctx.get("timestamp", 0) > _TTL_SEGUNDOS


def _rate_limited(user_id: int) -> bool:
    now = time.time()
    calls = [t for t in _user_timestamps[user_id] if now - t < _RATE_LIMIT_WINDOW]
    _user_timestamps[user_id] = calls
    if len(calls) >= _RATE_LIMIT_CALLS:
        return True
    _user_timestamps[user_id].append(now)
    return False


def _mensaje_error_amigable(e: Exception) -> str:
    msg = str(e).lower()
    if isinstance(e, asyncio.TimeoutError):
        return "La consulta tardó demasiado. Intentá con un requerimiento más específico o usá /nueva."
    if "429" in msg or "rate" in msg:
        return "El servicio está ocupado en este momento. Esperá unos segundos y volvé a intentar."
    if "connect" in msg or "connection" in msg or "errno 111" in msg:
        return "Hubo un problema de conexión. Intentá de nuevo en unos segundos."
    if "json" in msg or "parse" in msg:
        return "Hubo un problema procesando la respuesta. Reformulá el requerimiento y volvé a intentar."
    return "Algo salió mal. Si persiste, usá /nueva y reformulá el requerimiento."


# ── Menú inicial ──────────────────────────────────────────────────────────────

async def _mostrar_menu_inicio(message) -> None:
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Nueva cotización", callback_data="menu:cotizar"),
            InlineKeyboardButton("Buscar cliente", callback_data="menu:cliente"),
        ],
        [
            InlineKeyboardButton("Ver tarifas", callback_data="menu:tarifas"),
            InlineKeyboardButton("Ver ejemplos", callback_data="menu:ayuda"),
        ],
    ])
    await message.reply_text(
        "Hola! Soy el Cotizador Técnico de Fachmann.\n\n"
        "¿Qué querés hacer?",
        reply_markup=keyboard,
    )


# ── Comandos ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _mostrar_menu_inicio(update.message)


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Ejemplos de requerimientos que podés enviar:\n\n"
        "• \"Módulo seguridad para prensa dos manos categoría 4, cliente Techint\"\n"
        "• \"Relé para parada de emergencia PL e, planta Arcor Córdoba\"\n"
        "• \"Bandejas portacables para tablero 2m x 60cm, proyecto Molinos\"\n"
        "• \"Sistema configurable para 4 funciones de seguridad simultáneas\"\n\n"
        "Podés incluir el nombre del cliente para personalizar el email.\n\n"
        "Usá /tarifa para ver o cambiar la tarifa de descuento activa."
    )


async def cmd_nueva(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.message.reply_text("Listo, empezamos de nuevo. Describí el requerimiento.")


async def cmd_tarifa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        tarifa_actual = context.user_data.get("tarifa")
        if tarifa_actual:
            await update.message.reply_text(
                f"Tarifa activa: *{tarifa_actual}*\n\n"
                "Para cambiarla: /tarifa <nombre exacto>\n"
                "Para ver opciones: /tarifa lista",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "Sin tarifa activa — las cotizaciones usan precio de lista.\n\n"
                "Para activar: /tarifa <nombre exacto>\n"
                "Para ver opciones: /tarifa lista"
            )
        return

    nombre = " ".join(args).strip()
    if nombre.lower() == "lista":
        await update.message.reply_text(
            "Tarifas disponibles (copiá el nombre exacto):\n\n"
            "• Dist. Principal - Pilz 25% - Resto 30+10\n"
            "• 30% OBO - Cabur - Pilz 0%\n"
            "• Pilz System Partner - 30+10\n"
            "• End User (5%)\n\n"
            "Ejemplo: /tarifa Pilz System Partner - 30+10"
        )
        return

    context.user_data["tarifa"] = nombre
    await update.message.reply_text(
        f"Tarifa establecida: *{nombre}*\n"
        "Las próximas cotizaciones usarán esta tarifa.",
        parse_mode="Markdown"
    )


async def cmd_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text(
            "Uso: /cliente <nombre o parte del nombre>\n\nEjemplo: /cliente Arcor"
        )
        return

    empresa = " ".join(args).strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        clientes = await buscar_cliente(empresa)
    except Exception as e:
        logger.error("Error buscando cliente '%s': %s", empresa, e, exc_info=True)
        await update.message.reply_text("No pude consultar la base de datos. Intentá de nuevo.")
        return

    if not clientes:
        await update.message.reply_text(f"No encontré clientes que coincidan con '{empresa}'.")
        return

    for c in clientes:
        estado_emoji = {
            "nuevo_cliente": "🆕", "calificado": "✅", "oferta": "📋",
            "ganado": "🏆", "perdido": "❌", "cancelado": "🚫",
        }.get(c.get("estado_lead", ""), "•")

        lineas = [f"*{c['razon_social']}* {estado_emoji} {c.get('estado_lead', '')}"]
        if c.get("contacto_nombre"):
            cargo = f" — {c['contacto_cargo']}" if c.get("contacto_cargo") else ""
            lineas.append(f"Contacto: {c['contacto_nombre']}{cargo}")
        if c.get("contacto_email"):
            lineas.append(f"Email: {c['contacto_email']}")
        if c.get("contacto_telefono"):
            lineas.append(f"Tel: {c['contacto_telefono']}")
        if c.get("industria"):
            lineas.append(f"Industria: {c['industria']}")
        if c.get("notas"):
            lineas.append(f"\n_{c['notas']}_")

        ops = c.get("oportunidades_activas", [])
        if ops:
            lineas.append("\n*Oportunidades activas:*")
            for op in ops:
                monto = f"USD {op['monto_usd']:,.0f}" if op.get("monto_usd") else "—"
                lineas.append(
                    f"  • {op['descripcion'][:60]} | {op['etapa']} | {monto} | {op['probabilidad_cierre']}%"
                )

        ints = c.get("interacciones_recientes", [])
        if ints:
            lineas.append("\n*Últimas interacciones:*")
            for i in ints:
                fecha = i["fecha"][:10] if i.get("fecha") else ""
                lineas.append(f"  [{fecha}] {i['tipo'].upper()}: {i['notas'][:80]}")

        await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")


# ── Wizard de preguntas (inline keyboards) ────────────────────────────────────

def _normalizar_pregunta(p) -> dict:
    if isinstance(p, str):
        return {"texto": p, "opciones": [], "contexto": None, "no_se_asuncion": None}
    return p


def _ordenar_preguntas(preguntas: list) -> list:
    normalized = [_normalizar_pregunta(p) for p in preguntas]
    return sorted(normalized, key=lambda p: p.get("orden", 999))


def _construir_teclado(preg_idx: int, pregunta: dict) -> InlineKeyboardMarkup:
    opciones = pregunta.get("opciones") or []
    keyboard = []
    row = []
    for j, op in enumerate(opciones):
        row.append(InlineKeyboardButton(str(op), callback_data=f"q{preg_idx}:{j}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    if pregunta.get("no_se_asuncion"):
        keyboard.append([InlineKeyboardButton(
            "No sé / No tengo el dato", callback_data=f"q{preg_idx}:ns"
        )])
    return InlineKeyboardMarkup(keyboard)


async def _mostrar_pregunta(message, context: ContextTypes.DEFAULT_TYPE, idx: int) -> None:
    ctx = context.user_data["cotizacion_pendiente"]
    preguntas = ctx["preguntas_pendientes"]
    pregunta = preguntas[idx]
    total = len(preguntas)

    nivel = pregunta.get("nivel_criticidad", "")
    ref = pregunta.get("referencia_normativa", "")
    contexto_txt = pregunta.get("contexto")
    no_se = pregunta.get("no_se_asuncion")
    opciones = pregunta.get("opciones") or []

    header = f"*Pregunta {idx + 1}/{total}*"
    if nivel == "alta":
        sufijo = f"seguridad crítica — {ref}" if ref else "seguridad crítica"
        header += f" _({sufijo})_"
    elif ref:
        header += f" _({ref})_"

    msg = f"{header}\n\n{pregunta['texto']}"
    if contexto_txt:
        msg += f"\n\n_{contexto_txt}_"
    if no_se:
        asuncion_val = no_se.split("(")[0].strip()
        msg += f"\n\n_Si no tenés el dato, asumiremos: {asuncion_val}_"

    if not opciones and not no_se:
        msg += "\n\nRespondé en texto libre."
        await message.reply_text(msg, parse_mode="Markdown")
        return

    await message.reply_text(
        msg,
        reply_markup=_construir_teclado(idx, pregunta),
        parse_mode="Markdown"
    )


async def _iniciar_flujo_preguntas(
    message,
    context: ContextTypes.DEFAULT_TYPE,
    resultado: dict,
    requerimiento: str,
    cliente: str,
) -> None:
    preguntas = _ordenar_preguntas(resultado.get("preguntas", []))
    resumen = resultado.get("resumen_requerimiento", "")

    context.user_data["cotizacion_pendiente"] = {
        "requerimiento_original": requerimiento,
        "cliente": cliente,
        "preguntas_pendientes": preguntas,
        "respuestas": {},
        "pregunta_actual": 0,
        "timestamp": time.time(),
    }

    if resumen:
        await message.reply_text(
            f"Entendí: _{resumen}_\n\nTengo algunas preguntas:",
            parse_mode="Markdown"
        )
    if preguntas:
        await _mostrar_pregunta(message, context, 0)
    else:
        await message.reply_text("No hay preguntas pendientes. Podés describir el requerimiento de nuevo.")


async def _mostrar_confirmacion_wizard(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra resumen de respuestas del wizard con [Confirmar] / [Corregir] antes de llamar al LLM."""
    ctx = context.user_data.get("cotizacion_pendiente", {})
    respuestas = ctx.get("respuestas", {})

    if not respuestas:
        # Sin respuestas para confirmar — proceder directamente
        await _completar_cotizacion(message, context)
        return

    lineas = ["*Parámetros del requerimiento:*"]
    for k, v in respuestas.items():
        lineas.append(f"• {k}: {v}")
    lineas.append("\n¿Confirmás estos datos?")

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Confirmar", callback_data="wiz:confirmar"),
        InlineKeyboardButton("Corregir desde el inicio", callback_data="wiz:corregir"),
    ]])
    await message.reply_text("\n".join(lineas), reply_markup=keyboard, parse_mode="Markdown")


async def _completar_cotizacion(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Llama al cotizador con las respuestas del wizard. Usa el modelo de propuesta (Sonnet)."""
    ctx = context.user_data.pop("cotizacion_pendiente")
    requerimiento = ctx["requerimiento_original"]
    cliente = ctx["cliente"]
    tarifa = context.user_data.get("tarifa")
    respuestas = ctx.get("respuestas", {})

    if respuestas:
        respuestas_txt = "\n".join(f"- {k}: {v}" for k, v in respuestas.items())
        requerimiento_completo = requerimiento + f"\n\nInformación adicional:\n{respuestas_txt}"
    else:
        requerimiento_completo = requerimiento

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    try:
        resultado = await asyncio.wait_for(
            generar_cotizacion(
                requerimiento=requerimiento_completo,
                cliente=cliente,
                tarifa_nombre=tarifa,
                model=CLAUDE_MODEL_PROPUESTA,  # Modelo de mayor calidad post-wizard
            ),
            timeout=_COTIZACION_TIMEOUT,
        )
        await _despachar_resultado(message, context, resultado, requerimiento_completo, cliente)
    except Exception as e:
        logger.error("Error completando cotización: %s", e, exc_info=True)
        await message.reply_text(_mensaje_error_amigable(e))


# ── Confirmación pre-PDF y menú post-propuesta ────────────────────────────────

async def _mostrar_confirmacion_propuesta(
    message, context: ContextTypes.DEFAULT_TYPE, propuesta: dict
) -> None:
    """Muestra resumen de productos con [Generar PDF] / [Buscar alternativa] antes de enviar."""
    cliente = propuesta.get("cliente", "No especificado")
    productos = propuesta.get("productos", [])

    lineas = [f"*Propuesta para {cliente}*\n"]
    for p in productos:
        lineas.append(f"• `{p['sku']}` × {p['cantidad']} — USD {p['precio_usd']:.2f}")
        lineas.append(f"  _{p['descripcion'][:70]}_")
    lineas.append(f"\n*Total: USD {propuesta.get('total_usd', 0):.2f}*")
    norma = propuesta.get("norma_aplicable", "")
    if norma:
        lineas.append(f"Norma: {norma}")
    lineas.append(f"Entrega: {propuesta.get('tiempo_entrega_dias', 30)} días")

    context.user_data["propuesta_pendiente"] = propuesta

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Generar PDF", callback_data="prop:confirmar"),
        InlineKeyboardButton("Buscar alternativa", callback_data="prop:alternativa"),
    ]])
    await message.reply_text("\n".join(lineas), reply_markup=keyboard, parse_mode="Markdown")


async def _mostrar_menu_post_propuesta(message) -> None:
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Modificar cantidad", callback_data="action:modificar"),
            InlineKeyboardButton("Nueva cotización", callback_data="action:nueva"),
        ],
        [
            InlineKeyboardButton("Guardar en CRM", callback_data="action:crm"),
            InlineKeyboardButton("Cambiar tarifa", callback_data="action:tarifa"),
        ],
    ])
    await message.reply_text("¿Qué hacemos ahora?", reply_markup=keyboard)


async def _despachar_resultado(
    message,
    context: ContextTypes.DEFAULT_TYPE,
    resultado: dict,
    requerimiento: str,
    cliente: str,
) -> None:
    tipo = resultado.get("tipo")

    if tipo == "sin_resultado":
        mensaje = resultado.get("mensaje", "No se encontraron productos en el catálogo.")
        alternativas = resultado.get("alternativas", [])
        busquedas = resultado.get("busquedas_realizadas", [])

        txt = f"No encontré ese producto en el catálogo.\n\n{mensaje}"
        if busquedas:
            txt += f"\n\nBúsquedas realizadas: {', '.join(busquedas)}"
        if alternativas:
            txt += "\n\n*Alternativas posibles:*\n" + "\n".join(f"• {a}" for a in alternativas)
        txt += "\n\n¿Querés que cotice alguna de las alternativas, o tenés un SKU específico?"
        await message.reply_text(txt, parse_mode="Markdown")

    elif tipo == "preguntas":
        await _iniciar_flujo_preguntas(message, context, resultado, requerimiento, cliente)

    else:
        # Propuesta lista → mostrar confirmación pre-PDF
        await _mostrar_confirmacion_propuesta(message, context, resultado)


# ── Envío de propuesta ────────────────────────────────────────────────────────

def _siguiente_numero() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


async def _enviar_propuesta(message, propuesta: dict) -> None:
    numero = _siguiente_numero()
    cliente_nombre = propuesta.get("cliente", "cliente")

    pdf_enviado = False
    try:
        from src.pdf_generator import generar_pdf  # noqa: PLC0415
        pdf_bytes = generar_pdf(propuesta, numero_propuesta=numero)
        nombre_archivo = (
            f"propuesta_{cliente_nombre.replace(' ', '_')}"
            f"_{date.today().isoformat()}.pdf"
        )
        await message.reply_document(
            document=BytesIO(pdf_bytes),
            filename=nombre_archivo,
            caption=(
                f"Propuesta N° {numero} — {cliente_nombre}\n"
                f"Total: USD {propuesta.get('total_usd', 0):.2f}"
            )
        )
        pdf_enviado = True
    except Exception as pdf_err:
        logger.warning("PDF no disponible en este entorno (%s). Enviando texto.", pdf_err)

    if not pdf_enviado:
        productos_txt = "\n".join(
            f"  • `{p['sku']}` × {p['cantidad']} — USD {p['precio_usd']:.2f}\n"
            f"    {p['descripcion']}"
            for p in propuesta.get("productos", [])
        )
        await message.reply_text(
            f"*Propuesta N° {numero} — {cliente_nombre}*\n\n"
            f"*Productos:*\n{productos_txt}\n\n"
            f"*Total: USD {propuesta.get('total_usd', 0):.2f}*\n"
            f"Norma: {propuesta.get('norma_aplicable', '')}\n"
            f"Entrega: {propuesta.get('tiempo_entrega_dias', 30)} días\n\n"
            f"_(PDF disponible en producción Railway)_",
            parse_mode="Markdown"
        )

    email_draft = propuesta.get("email_draft", "")
    if email_draft:
        await message.reply_text(
            f"*Borrador de email:*\n\n{email_draft}",
            parse_mode="Markdown"
        )


# ── Handlers de callbacks (router por prefijo) ────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if re.match(r"q\d+:", data):
        await _cb_wizard_pregunta(query, context, data)
    elif data.startswith("wiz:"):
        await _cb_wizard_confirmacion(query, context, data[4:])
    elif data.startswith("prop:"):
        await _cb_prop_confirmacion(query, context, data[5:])
    elif data.startswith("action:"):
        await _cb_accion(query, context, data[7:])
    elif data.startswith("menu:"):
        await _cb_menu(query, context, data[5:])


async def _cb_wizard_pregunta(query, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """Procesa la respuesta a una pregunta del wizard."""
    ctx = context.user_data.get("cotizacion_pendiente")

    if not ctx or _estado_expirado(ctx):
        context.user_data.pop("cotizacion_pendiente", None)
        await query.message.reply_text(
            "La sesión expiró (30 min). Describí el requerimiento de nuevo."
        )
        return

    match = re.match(r"q(\d+):(\d+|ns)$", data)
    if not match:
        return

    preg_idx = int(match.group(1))
    opcion_raw = match.group(2)
    preguntas = ctx["preguntas_pendientes"]

    if preg_idx >= len(preguntas):
        return

    pregunta = preguntas[preg_idx]

    if opcion_raw == "ns":
        no_se = pregunta.get("no_se_asuncion") or "No especificado"
        valor = no_se.split("(")[0].strip()
    else:
        opcion_idx = int(opcion_raw)
        opciones = pregunta.get("opciones") or []
        if opcion_idx >= len(opciones):
            return
        valor = str(opciones[opcion_idx])

    codigo = pregunta.get("codigo_parametro") or pregunta.get("texto", f"param_{preg_idx}")[:40]
    ctx["respuestas"][codigo] = valor
    ctx["pregunta_actual"] = preg_idx + 1

    siguiente = preg_idx + 1
    if siguiente < len(preguntas):
        await _mostrar_pregunta(query.message, context, siguiente)
    else:
        # Wizard completo → mostrar resumen para confirmar antes de llamar al LLM
        await _mostrar_confirmacion_wizard(query.message, context)


async def _cb_wizard_confirmacion(query, context: ContextTypes.DEFAULT_TYPE, accion: str) -> None:
    if accion == "confirmar":
        await query.message.reply_text("Procesando con la información adicional...")
        await _completar_cotizacion(query.message, context)
    elif accion == "corregir":
        ctx = context.user_data.get("cotizacion_pendiente")
        if ctx:
            ctx["respuestas"] = {}
            ctx["pregunta_actual"] = 0
            ctx["timestamp"] = time.time()
            await query.message.reply_text("De acuerdo, empezamos de nuevo las preguntas.")
            await _mostrar_pregunta(query.message, context, 0)
        else:
            await query.message.reply_text("La sesión expiró. Describí el requerimiento de nuevo.")


async def _cb_prop_confirmacion(query, context: ContextTypes.DEFAULT_TYPE, accion: str) -> None:
    if accion == "confirmar":
        propuesta = context.user_data.pop("propuesta_pendiente", None)
        if not propuesta:
            await query.message.reply_text(
                "No hay propuesta pendiente. Describí el requerimiento de nuevo."
            )
            return
        context.user_data["ultima_propuesta"] = propuesta
        await _enviar_propuesta(query.message, propuesta)
        await _mostrar_menu_post_propuesta(query.message)

    elif accion == "alternativa":
        propuesta = context.user_data.pop("propuesta_pendiente", None)
        if propuesta:
            context.user_data["refinamiento_ctx"] = _resumen_propuesta(propuesta)
        await query.message.reply_text(
            "¿Qué querés cambiar? Describilo en texto libre.\n\n"
            "Ejemplo: \"Necesito versión para 110 VAC\" o \"Buscar de otra familia de producto\""
        )


async def _cb_menu(query, context: ContextTypes.DEFAULT_TYPE, accion: str) -> None:
    if accion == "cotizar":
        await query.message.reply_text(
            "Describí el requerimiento técnico del cliente y te genero la propuesta.\n\n"
            "Ejemplo: \"Prensa con control de dos manos, categoría 4, cliente Arcor\""
        )
    elif accion == "cliente":
        await query.message.reply_text(
            "¿Qué cliente querés buscar? Escribí el nombre o parte del nombre.\n\n"
            "Ejemplo: escribí *Arcor* o usá /cliente Arcor",
            parse_mode="Markdown",
        )
    elif accion == "tarifas":
        tarifa_activa = context.user_data.get("tarifa")
        activa_txt = f"\nActiva ahora: *{tarifa_activa}*" if tarifa_activa else "\nSin tarifa activa (precio de lista)."
        await query.message.reply_text(
            "Tarifas disponibles:\n\n"
            "• Dist. Principal - Pilz 25% - Resto 30+10\n"
            "• 30% OBO - Cabur - Pilz 0%\n"
            "• Pilz System Partner - 30+10\n"
            "• End User (5%)\n"
            f"{activa_txt}\n\n"
            "Para activar: /tarifa <nombre exacto>",
            parse_mode="Markdown",
        )
    elif accion == "ayuda":
        await query.message.reply_text(
            "Ejemplos de requerimientos:\n\n"
            "• \"Módulo seguridad para prensa dos manos categoría 4, cliente Techint\"\n"
            "• \"Relé para parada de emergencia PL e, planta Arcor Córdoba\"\n"
            "• \"Bandejas portacables para tablero 2m x 60cm, proyecto Molinos\"\n"
            "• \"Sistema configurable para 4 funciones de seguridad simultáneas\"\n\n"
            "Podés mencionar el cliente en el texto para personalizar el email.\n"
            "Usá /nueva en cualquier momento para cancelar y empezar de cero."
        )


async def _cb_accion(query, context: ContextTypes.DEFAULT_TYPE, accion: str) -> None:
    if accion == "nueva":
        context.user_data.pop("ultima_propuesta", None)
        context.user_data.pop("propuesta_pendiente", None)
        context.user_data.pop("cotizacion_pendiente", None)
        context.user_data.pop("refinamiento_ctx", None)
        await query.message.reply_text("Listo. Describí el nuevo requerimiento.")

    elif accion == "modificar":
        ultima = context.user_data.get("ultima_propuesta")
        if not ultima:
            await query.message.reply_text("No hay propuesta anterior para modificar.")
            return
        productos = ultima.get("productos", [])
        items_txt = "\n".join(f"  • {p['sku']} × {p['cantidad']}" for p in productos)
        await query.message.reply_text(
            f"Productos de la propuesta anterior:\n{items_txt}\n\n"
            "Escribí la modificación que necesitás. Ejemplos:\n"
            "• \"Cambiá el PNOZ-S6 a 3 unidades\"\n"
            "• \"Agregá 2 borneras de 10mm2\"\n"
            "• \"Cambiá el cliente a Techint\""
        )

    elif accion == "crm":
        ultima = context.user_data.get("ultima_propuesta")
        cliente_nombre = ultima.get("cliente") if ultima else None
        if not ultima or not cliente_nombre or cliente_nombre == "No especificado":
            await query.message.reply_text(
                "No hay cliente asociado a la propuesta.\n"
                "Usá /cliente <nombre> para ver el perfil del cliente."
            )
            return
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        productos_txt = ", ".join(
            f"{p['sku']} x{p['cantidad']}"
            for p in ultima.get("productos", [])[:5]
        )
        notas = f"Cotización: {productos_txt}. Total: USD {ultima.get('total_usd', 0):.2f}"
        try:
            resultado = await registrar_interaccion(
                cliente_nombre=cliente_nombre,
                notas=notas,
                tipo="cotizacion",
            )
            if resultado.get("error"):
                await query.message.reply_text(
                    f"No encontré a *{cliente_nombre}* en el CRM.",
                    parse_mode="Markdown"
                )
            else:
                await query.message.reply_text(
                    f"Guardado en CRM para *{resultado['cliente']}*.",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error("Error guardando en CRM: %s", e, exc_info=True)
            await query.message.reply_text("No se pudo guardar en el CRM. Intentá de nuevo.")

    elif accion == "tarifa":
        await query.message.reply_text(
            "Tarifas disponibles (usá /tarifa <nombre> para activar):\n\n"
            "• Dist. Principal - Pilz 25% - Resto 30+10\n"
            "• 30% OBO - Cabur - Pilz 0%\n"
            "• Pilz System Partner - 30+10\n"
            "• End User (5%)"
        )


# ── Handler principal de texto ────────────────────────────────────────────────

async def handle_requerimiento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = update.message.text.strip()
    if not texto:
        return

    # Rate limiting
    if _rate_limited(update.effective_user.id):
        await update.message.reply_text("Estás enviando mensajes muy rápido. Esperá un momento.")
        return

    # Input trivial (saludo, "ok", texto muy corto) → mostrar menú inicio
    if _es_input_trivial(texto):
        await _mostrar_menu_inicio(update.message)
        return

    # Si hay un wizard con pregunta de texto libre activa → procesar como respuesta
    ctx_pendiente = context.user_data.get("cotizacion_pendiente")
    if ctx_pendiente and not _estado_expirado(ctx_pendiente):
        idx = ctx_pendiente.get("pregunta_actual", 0)
        preguntas = ctx_pendiente.get("preguntas_pendientes", [])
        if idx < len(preguntas):
            pregunta = preguntas[idx]
            if not (pregunta.get("opciones") or pregunta.get("no_se_asuncion")):
                codigo = pregunta.get("codigo_parametro") or pregunta.get("texto", f"param_{idx}")[:40]
                ctx_pendiente["respuestas"][codigo] = texto
                ctx_pendiente["pregunta_actual"] = idx + 1
                siguiente = idx + 1
                if siguiente < len(preguntas):
                    await _mostrar_pregunta(update.message, context, siguiente)
                else:
                    await _mostrar_confirmacion_wizard(update.message, context)
                return

        # Wizard activo pero el usuario manda un requerimiento nuevo → cancelar
        context.user_data.pop("cotizacion_pendiente", None)
        await update.message.reply_text(
            "Cancelé la cotización anterior. Procesando el nuevo requerimiento..."
        )

    # Contexto de "Buscar alternativa" (de prop:alternativa)
    refinamiento_ctx = context.user_data.pop("refinamiento_ctx", None)

    # Multi-turno: ¿el usuario quiere modificar la propuesta anterior?
    ultima = context.user_data.get("ultima_propuesta")
    model_a_usar = None  # Haiku por default

    if refinamiento_ctx:
        requerimiento_a_usar = refinamiento_ctx + f"\n\nBUSCAR ALTERNATIVA: {texto}"
        model_a_usar = CLAUDE_MODEL_PROPUESTA
    elif _es_refinamiento(texto, ultima):
        requerimiento_a_usar = _resumen_propuesta(ultima) + f"\n\nMODIFICACIÓN: {texto}"
        model_a_usar = CLAUDE_MODEL_PROPUESTA
    else:
        requerimiento_a_usar = texto

    # Extracción de cliente del texto libre
    cliente = _extraer_cliente(texto)

    tarifa_activa = context.user_data.get("tarifa")
    await update.message.reply_text("Consultando catálogo y preparando propuesta...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        resultado = await asyncio.wait_for(
            generar_cotizacion(
                requerimiento=requerimiento_a_usar,
                cliente=cliente,
                tarifa_nombre=tarifa_activa,
                model=model_a_usar,
            ),
            timeout=_COTIZACION_TIMEOUT,
        )
        await _despachar_resultado(update.message, context, resultado, requerimiento_a_usar, cliente)
    except Exception as e:
        context.user_data.pop("cotizacion_pendiente", None)
        logger.error("Error procesando requerimiento: %s", e, exc_info=True)
        await update.message.reply_text(_mensaje_error_amigable(e))


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde a mensajes no-texto (fotos, stickers, voz, etc.)."""
    await update.message.reply_text(
        "Solo proceso mensajes de texto. Describí el requerimiento técnico en palabras.\n\n"
        "Ejemplo: \"Relé de seguridad para parada de emergencia PL e, cliente Arcor\""
    )


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Error no capturado: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Ocurrió un error inesperado. Usá /nueva para reiniciar si el problema persiste."
        )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN no configurado en .env")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("tarifa", cmd_tarifa))
    app.add_handler(CommandHandler("cliente", cmd_cliente))
    app.add_handler(CommandHandler("nueva", cmd_nueva))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_requerimiento))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, handle_media))

    app.add_error_handler(handle_error)

    logger.info("Bot Fachmann iniciado...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
