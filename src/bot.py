"""
Telegram bot para el Cotizador Técnico Fachmann.
Recibe requerimientos en lenguaje natural y devuelve propuesta PDF + email draft.
"""

import logging
import os
import sys
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

# Asegurar que la raíz del proyecto esté en sys.path
# (necesario cuando se corre con `python src/bot.py`)
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from src.cotizador import buscar_cliente, generar_cotizacion

load_dotenv()

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


def _siguiente_numero() -> str:
    """Número de propuesta basado en timestamp — único y no se resetea en reinicios."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


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
        "/tarifa — ver o cambiar tarifa de descuento activa"
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


async def cmd_tarifa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra o establece la tarifa de descuento activa para esta sesión."""
    args = context.args  # texto después de /tarifa

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
    await update.message.reply_text(f"Buscando '{empresa}'...")

    try:
        clientes = await buscar_cliente(empresa)
    except Exception as e:
        await update.message.reply_text(f"Error al buscar: {e}")
        return

    if not clientes:
        await update.message.reply_text(f"No encontré clientes que coincidan con '{empresa}'.")
        return

    for c in clientes:
        estado_emoji = {
            "nuevo_cliente": "🆕", "calificado": "✅", "oferta": "📋",
            "ganado": "🏆", "perdido": "❌", "cancelado": "🚫",
        }.get(c.get("estado_lead", ""), "•")

        lineas = [
            f"*{c['razon_social']}* {estado_emoji} {c.get('estado_lead', '')}",
        ]
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


async def _enviar_propuesta(update: Update, propuesta: dict) -> None:
    """Genera y envía el PDF (o fallback texto) + borrador de email."""
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
        await update.message.reply_document(
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
        await update.message.reply_text(
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
        await update.message.reply_text(
            f"*Borrador de email:*\n\n{email_draft}",
            parse_mode="Markdown"
        )


async def handle_requerimiento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler principal: procesa el requerimiento y devuelve PDF + email.

    Flujo conversacional:
    - Si el cotizador necesita más info, envía preguntas al usuario y espera.
    - La respuesta del usuario se concatena al requerimiento original y se reintenta.
    - El contexto se limpia después de entregar la propuesta o ante un nuevo requerimiento.
    """
    texto = update.message.text.strip()
    if not texto:
        return

    tarifa_activa = context.user_data.get("tarifa")

    # ── Flujo conversacional: si hay preguntas pendientes, combinar respuesta ──
    ctx_pendiente = context.user_data.get("cotizacion_pendiente")
    if ctx_pendiente:
        requerimiento_completo = (
            ctx_pendiente["requerimiento_original"]
            + "\n\nRespuestas a las preguntas:\n"
            + texto
        )
        cliente = ctx_pendiente.get("cliente", "No especificado")
        context.user_data.pop("cotizacion_pendiente", None)
        await update.message.reply_text("Procesando con la información adicional...")
    else:
        requerimiento_completo = texto
        cliente = "No especificado"
        await update.message.reply_text(
            "Consultando catálogo y preparando propuesta..."
        )

    try:
        resultado = await generar_cotizacion(
            requerimiento=requerimiento_completo,
            cliente=cliente,
            tarifa_nombre=tarifa_activa,
        )

        # ── Respuesta tipo: sin resultado en catálogo ─────────────────────────
        if resultado.get("tipo") == "sin_resultado":
            mensaje = resultado.get("mensaje", "No se encontraron productos en el catálogo.")
            alternativas = resultado.get("alternativas", [])
            busquedas = resultado.get("busquedas_realizadas", [])

            txt = f"No encontré ese producto en el catálogo.\n\n{mensaje}"
            if busquedas:
                txt += f"\n\nBúsquedas realizadas: {', '.join(busquedas)}"
            if alternativas:
                txt += "\n\n*Alternativas posibles:*\n" + "\n".join(f"• {a}" for a in alternativas)
            txt += "\n\n¿Querés que cotice alguna de las alternativas, o tenés un SKU específico?"
            await update.message.reply_text(txt, parse_mode="Markdown")
            return

        # ── Respuesta tipo: preguntas de clarificación ─────────────────────────
        if resultado.get("tipo") == "preguntas":
            preguntas = resultado.get("preguntas", [])
            resumen = resultado.get("resumen_requerimiento", "")

            # Guardar contexto para la próxima respuesta
            context.user_data["cotizacion_pendiente"] = {
                "requerimiento_original": requerimiento_completo,
                "cliente": cliente,
            }

            preguntas_txt = "\n".join(f"{i+1}. {p}" for i, p in enumerate(preguntas))
            msg = ""
            if resumen:
                msg += f"Entendí: _{resumen}_\n\n"
            msg += f"Necesito un poco más de información:\n\n{preguntas_txt}\n\nRespondé todo en un solo mensaje."
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

        # ── Respuesta tipo: propuesta completa ────────────────────────────────
        await _enviar_propuesta(update, resultado)

    except Exception as e:
        context.user_data.pop("cotizacion_pendiente", None)
        logger.error("Error procesando requerimiento: %s", e, exc_info=True)
        await update.message.reply_text(
            f"Error al generar la propuesta: {e}\n"
            "Intentá reformular el requerimiento o contactá al administrador."
        )


def main() -> None:
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN no configurado en .env")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("tarifa", cmd_tarifa))
    app.add_handler(CommandHandler("cliente", cmd_cliente))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_requerimiento))

    logger.info("Bot Fachmann iniciado...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
