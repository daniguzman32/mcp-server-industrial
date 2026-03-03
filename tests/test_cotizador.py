import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_cotizador_devuelve_json_estructurado():
    """El cotizador debe devolver JSON con campos obligatorios."""
    from src.cotizador import generar_cotizacion

    mock_response = {
        "cliente": "Arcor",
        "requerimiento": "Prensa dos manos cat 4",
        "productos": [
            {
                "sku": "PNOZ-XV2-24VDC",
                "descripcion": "Relé de seguridad PNOZ XV2",
                "cantidad": 1,
                "precio_usd": 320.0,
                "justificacion": "ISO 13849 PL e Cat 4"
            }
        ],
        "norma_aplicable": "ISO 13849-1:2015 PL e, Categoría 4",
        "total_usd": 320.0,
        "validez_dias": 30,
        "tiempo_entrega_dias": 21,
        "email_draft": "Estimado Ing. Martínez..."
    }

    with patch("src.cotizador.llamar_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = mock_response
        resultado = await generar_cotizacion(
            requerimiento="Prensa dos manos cat 4",
            cliente="Arcor"
        )

    assert "productos" in resultado
    assert "total_usd" in resultado
    assert "email_draft" in resultado
    assert "norma_aplicable" in resultado
    assert resultado["total_usd"] > 0


def test_pdf_generator_retorna_bytes():
    """El generador debe retornar bytes de un PDF válido."""
    from src.pdf_generator import generar_pdf

    propuesta = {
        "cliente": "Arcor S.A.I.C.",
        "requerimiento": "Módulo seguridad prensa dos manos",
        "productos": [
            {
                "sku": "PNOZ-XV2-24VDC",
                "descripcion": "Relé de seguridad PNOZ XV2",
                "cantidad": 1,
                "precio_usd": 320.0,
                "justificacion": "ISO 13849 PL e Cat 4"
            }
        ],
        "norma_aplicable": "ISO 13849-1:2015 PL e, Categoría 4",
        "total_usd": 320.0,
        "validez_dias": 30,
        "tiempo_entrega_dias": 21,
        "notas_tecnicas": "",
        "email_draft": "Estimado Ing. Martínez..."
    }

    pdf_bytes = generar_pdf(propuesta, numero_propuesta="2026-001")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000          # Un PDF vacío no existe
    assert pdf_bytes[:4] == b"%PDF"       # Magic bytes de PDF
