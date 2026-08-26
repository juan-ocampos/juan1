"""Proveedor ElevenLabs: la mayor calidad de voz, de pago.

La voz se indica con su identificador (`voice_id`), que se obtiene con
`voceo voces --proveedor elevenlabs`. Requiere `ELEVENLABS_API_KEY`.
"""

from __future__ import annotations

import re
from pathlib import Path

from voceo.config import clave_api
from voceo.errores import ErrorDeSintesis, ProveedorNoDisponible
from voceo.proveedores.base import Proveedor, Voz

MODELO_POR_DEFECTO = "eleven_multilingual_v2"


def _factor_velocidad(porcentaje: str) -> float:
    coincidencia = re.match(r"^([+-]?\d{1,3})%$", porcentaje.strip())
    if not coincidencia:
        return 1.0
    # ElevenLabs solo admite un margen estrecho alrededor de la velocidad normal.
    return max(0.7, min(1.0 + int(coincidencia.group(1)) / 100, 1.2))


class ElevenLabsTTS(Proveedor):
    nombre = "elevenlabs"
    formato = "mp3"
    sin_conexion = False

    def _cliente(self):
        try:
            from elevenlabs.client import ElevenLabs  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depende del entorno
            raise ProveedorNoDisponible(
                "Falta la dependencia «elevenlabs». Instálala con:\n"
                "    pip install elevenlabs"
            ) from exc
        return ElevenLabs(api_key=clave_api("ELEVENLABS_API_KEY", self.nombre))

    def verificar(self) -> None:
        self._cliente()

    def sintetizar(self, texto: str, destino: Path) -> Path:
        cliente = self._cliente()
        destino = self._destino_con_formato(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)

        parametros = {
            "voice_id": self.config.voz,
            "text": texto,
            "model_id": self.config.modelo or MODELO_POR_DEFECTO,
            "output_format": "mp3_44100_128",
        }
        velocidad = _factor_velocidad(self.config.velocidad)
        if velocidad != 1.0:
            parametros["voice_settings"] = {"speed": velocidad}

        try:
            trozos = cliente.text_to_speech.convert(**parametros)
        except TypeError:
            # Versiones antiguas del SDK no aceptan `voice_settings` como dict.
            parametros.pop("voice_settings", None)
            trozos = cliente.text_to_speech.convert(**parametros)
        except Exception as exc:
            raise ErrorDeSintesis(f"ElevenLabs no pudo generar el audio: {exc}") from exc

        try:
            with destino.open("wb") as archivo:
                for trozo in trozos:
                    if trozo:
                        archivo.write(trozo)
        except Exception as exc:
            destino.unlink(missing_ok=True)
            raise ErrorDeSintesis(f"Error al escribir el audio: {exc}") from exc
        return destino

    def voces(self, idioma: str | None = "es") -> list[Voz]:
        cliente = self._cliente()
        try:
            respuesta = cliente.voices.get_all()
        except Exception as exc:
            raise ErrorDeSintesis(f"No se pudo consultar el catálogo: {exc}") from exc

        encontradas: list[Voz] = []
        for voz in getattr(respuesta, "voices", []) or []:
            etiquetas = getattr(voz, "labels", {}) or {}
            encontradas.append(
                Voz(
                    id=getattr(voz, "voice_id", ""),
                    nombre=getattr(voz, "name", ""),
                    idioma=str(etiquetas.get("language", "")),
                    genero=str(etiquetas.get("gender", "")),
                    descripcion=str(etiquetas.get("description", "")),
                )
            )
        return encontradas
