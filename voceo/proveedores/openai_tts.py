"""Proveedor OpenAI TTS.

Permite describir el estilo de lectura con `instrucciones`, algo muy útil
para el voceo: «tono cordial y pausado, como una anfitriona de centro
comercial». Requiere la variable de entorno `OPENAI_API_KEY`.
"""

from __future__ import annotations

import re
from pathlib import Path

from voceo.config import clave_api
from voceo.errores import ErrorDeSintesis, ProveedorNoDisponible
from voceo.proveedores.base import Proveedor, Voz

MODELO_POR_DEFECTO = "gpt-4o-mini-tts"

#: Voces del catálogo de OpenAI (sirven para cualquier idioma).
VOCES = [
    Voz("alloy", "Alloy", "multi", "", "neutra y equilibrada"),
    Voz("ash", "Ash", "multi", "", "grave y serena"),
    Voz("ballad", "Ballad", "multi", "", "cálida y expresiva"),
    Voz("coral", "Coral", "multi", "", "clara y amable"),
    Voz("echo", "Echo", "multi", "", "firme, buena para avisos"),
    Voz("fable", "Fable", "multi", "", "narrativa"),
    Voz("nova", "Nova", "multi", "", "brillante y cercana"),
    Voz("onyx", "Onyx", "multi", "", "profunda y autoritaria"),
    Voz("sage", "Sage", "multi", "", "tranquila"),
    Voz("shimmer", "Shimmer", "multi", "", "luminosa"),
]


def _factor_velocidad(porcentaje: str) -> float:
    """Convierte «-10%» en 0.9, que es lo que espera la API."""
    coincidencia = re.match(r"^([+-]?\d{1,3})%$", porcentaje.strip())
    if not coincidencia:
        return 1.0
    factor = 1.0 + int(coincidencia.group(1)) / 100
    return max(0.25, min(factor, 4.0))


class OpenAITTS(Proveedor):
    nombre = "openai"
    formato = "mp3"
    sin_conexion = False

    def _cliente(self):
        try:
            from openai import OpenAI  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depende del entorno
            raise ProveedorNoDisponible(
                "Falta la dependencia «openai». Instálala con:\n"
                "    pip install openai"
            ) from exc
        return OpenAI(api_key=clave_api("OPENAI_API_KEY", self.nombre))

    def verificar(self) -> None:
        self._cliente()

    def sintetizar(self, texto: str, destino: Path) -> Path:
        cliente = self._cliente()
        destino = self._destino_con_formato(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)

        parametros = {
            "model": self.config.modelo or MODELO_POR_DEFECTO,
            "voice": self.config.voz,
            "input": texto,
            "response_format": "mp3",
            "speed": _factor_velocidad(self.config.velocidad),
        }
        if self.config.instrucciones:
            parametros["instructions"] = self.config.instrucciones

        try:
            with cliente.audio.speech.with_streaming_response.create(
                **parametros
            ) as respuesta:
                respuesta.stream_to_file(destino)
        except Exception as exc:
            destino.unlink(missing_ok=True)
            raise ErrorDeSintesis(f"OpenAI no pudo generar el audio: {exc}") from exc
        return destino

    def voces(self, idioma: str | None = "es") -> list[Voz]:
        # El catálogo es fijo y multilingüe: el idioma lo marca el texto.
        return list(VOCES)
