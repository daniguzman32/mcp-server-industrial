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
from src.cotizador import buscar_cliente, generar_cotizacion

load_dotenv()

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

_TTL_SEGUNDOS = 1800        # 30 minutos — expiración de estado del wizard
_COTIZACION_TIMEOUT = 120   # segundos — timeout de llamada al cotizador

# Rate limiting: máx 5 mensajes por usuario en 10 segundos
_RATE_LIMIT_CALLS = 5
_RATE_LIMIT_WINDOW = 10
_user_timestamps: dict[int, list[float]] = defaultdict(list)


# ── Helpers internos ──────────────────────────────────────────────────────────

def _siguiente_numero() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _estado_expirado(ctx: dict) -> bool:
    return time.time() - ctx.get("timestamp", 0) > _TTL_SEGUNDOS


def _rate_limited(user_id: int) -> bool:
    """Retorna True si el usuario superó el límite de mensajes."""
    now = time.time()
    calls = [t for t in _user_timestamps[user_id] if now - t < _RATE_LIMIT_WINDOW]
    _user_timestamps[user_id] = calls
    if len(calls) >= _RATE_LIMIT_CALLS:
        return True
    _user_timestamps[user_id].append(now)
    return False


def _mensaje_error_amigable(e: Exception) -> str:
    """Convierte una excepción técnica en un mensaje comprensible para el usuario."""
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


# ── Comandos ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hola! Soy el Cotizador Técnico de Fachmann.\n\n"
        "Describí el requerimiento técnico del cliente y te genero la propuesta.\n\n"
        "Ejemplo:\n"
        "\"Prensa con control de dos manos, categoría 4, cliente Arcor\"\n\n"
        "Comandos:\n"
        "/start — este mensaje\n"
        "/ayuda — ejemplos de requerimientos\n"
        "/cliente <nombre> — perfil + historial de un cliente\n"
        "/tarifa — ver o cambiar tarifa de descuento activa\n"
        "/nueva — cancelar cotización en curso y empezar de nuevo"
    )


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
    """Cancela el flujo en curso y permite empezar de cero."""
    context.user_data.clear()
    await update.message.reply_text("Listo, empezamos de nuevo. Describí el requerimiento.")


async def cmd_tarifa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra o establece la tarifa de descuento activa para esta sesión."""
    args = context.args

    if not args:
        tarifa_actual = context.user_data.get("tarifa")
        if tarifa_actual:
            await update.message.reply_text(
                f"Tarifa activa: *{tarifa_actual}*\n\n"
                "Para cambiarla: /tarifa <nombre exacto>\n"
                "Para ver opciones enviá: /tarifa lista",
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
    """Muestra el perfil completo de un cliente con historial e interacciones."""
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
    """Garantiza que la pregunta sea dict con los campos mínimos."""
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

    # Sin opciones → texto libre (Claude no siguió el nuevo formato)
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


async def _completar_cotizacion(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resubmite al cotizador con las respuestas acumuladas del wizard."""
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
            ),
            timeout=_COTIZACION_TIMEOUT,
        )
        await _despachar_resultado(message, context, resultado, requerimiento_completo, cliente)
    except Exception as e:
        logger.error("Error completando cotización: %s", e, exc_info=True)
        await message.reply_text(_mensaje_error_amigable(e))


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
        await _enviar_propuesta(message, resultado)


# ── Envío de propuesta ────────────────────────────────────────────────────────

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


# ── Handlers principales ──────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa los clicks en los botones inline del wizard de preguntas."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
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
        await query.message.reply_text("Procesando con la información adicional...")
        await _completar_cotizacion(query.message, context)


async def handle_requerimiento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler principal: recibe texto libre y dispara el cotizador."""
    texto = update.message.text.strip()
    if not texto:
        return

    # Rate limiting
    if _rate_limited(update.effective_user.id):
        await update.message.reply_text("Estás enviando mensajes muy rápido. Esperá un momento.")
        return

    # Si hay un wizard activo con una pregunta sin opciones (texto libre), procesar como respuesta
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
                    await update.message.reply_text("Procesando con la información adicional...")
                    await _completar_cotizacion(update.message, context)
                return

        # Wizard activo pero el usuario manda un requerimiento nuevo → cancelar
        context.user_data.pop("cotizacion_pendiente", None)
        await update.message.reply_text(
            "Cancelé la cotización anterior. Procesando el nuevo requerimiento..."
        )

    tarifa_activa = context.user_data.get("tarifa")
    await update.message.reply_text("Consultando catálogo y preparando propuesta...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        resultado = await asyncio.wait_for(
            generar_cotizacion(
                requerimiento=texto,
                cliente="No especificado",
                tarifa_nombre=tarifa_activa,
            ),
            timeout=_COTIZACION_TIMEOUT,
        )
        await _despachar_resultado(update.message, context, resultado, texto, "No especificado")
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
    """Handler global de errores no capturados — evita que el bot muera en silencio."""
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
