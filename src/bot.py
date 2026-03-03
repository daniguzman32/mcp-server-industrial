"""
Telegram bot para el Cotizador Técnico Fachmann.
Recibe requerimientos en lenguaje natural y devuelve propuesta PDF + email draft.
"""

import logging
import os
import sys
from datetime import date
from io import BytesIO
from pathlib import Path

# Asegurar que la raíz del proyecto esté en sys.path
# (necesario cuando se corre con `python src/bot.py`)
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from src.cotizador import generar_cotizacion

load_dotenv()

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
_propuesta_counter = 0


def _siguiente_numero() -> str:
    global _propuesta_counter
    _propuesta_counter += 1
    return f"{date.today().year}-{_propuesta_counter:03d}"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hola! Soy el Cotizador Técnico de Fachmann.\n\n"
        "Describí el requerimiento técnico del cliente y te genero la propuesta.\n\n"
        "Ejemplo:\n"
        "\"Prensa con control de dos manos, categoría 4, cliente Arcor\"\n\n"
        "Comandos:\n"
        "/start — este mensaje\n"
        "/ayuda — ejemplos de requerimientos"
    )


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Ejemplos de requerimientos que podés enviar:\n\n"
        "• \"Módulo seguridad para prensa dos manos categoría 4, cliente Techint\"\n"
        "• \"Relé para parada de emergencia PL e, planta Arcor Córdoba\"\n"
        "• \"Bandejas portacables para tablero 2m x 60cm, proyecto Molinos\"\n"
        "• \"Sistema configurable para 4 funciones de seguridad simultáneas\"\n\n"
        "Podés incluir el nombre del cliente para personalizar el email."
    )


async def handle_requerimiento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler principal: procesa el requerimiento y devuelve PDF + email."""
    texto = update.message.text.strip()
    if not texto:
        return

    await update.message.reply_text(
        "Procesando requerimiento... Consultando catálogo y generando propuesta."
    )

    try:
        propuesta = await generar_cotizacion(
            requerimiento=texto,
            cliente="No especificado"
        )

        numero = _siguiente_numero()
        cliente_nombre = propuesta.get("cliente", "cliente")

        # Intentar generar PDF (falla en Windows sin GTK3, funciona en Railway/Linux)
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

        # Fallback: resumen en texto si no hay PDF (ej. Windows local)
        if not pdf_enviado:
            productos_txt = "\n".join(
                f"  • {p['sku']} × {p['cantidad']} — USD {p['precio_usd']:.2f}\n"
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

    except Exception as e:
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_requerimiento))

    logger.info("Bot Fachmann iniciado...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
