"""
Generador de PDF para propuestas técnicas Fachmann.
Usa Jinja2 para renderizar HTML y weasyprint para convertir a PDF.
"""

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATES_DIR = Path(__file__).parent / "templates"

_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def generar_pdf(propuesta: dict, numero_propuesta: str) -> bytes:
    """
    Recibe el dict de propuesta generado por cotizador.py y devuelve bytes del PDF.

    Args:
        propuesta: dict con keys: cliente, requerimiento, productos, norma_aplicable,
                   total_usd, validez_dias, tiempo_entrega_dias, notas_tecnicas
        numero_propuesta: string identificador (ej. "2026-042")

    Returns:
        bytes: contenido del PDF listo para enviar por Telegram o guardar
    """
    template = _jinja_env.get_template("propuesta.html")
    html_content = template.render(
        propuesta=propuesta,
        numero_propuesta=numero_propuesta,
        fecha=date.today().strftime("%d/%m/%Y")
    )
    return HTML(string=html_content).write_pdf()
