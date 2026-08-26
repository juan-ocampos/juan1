"""Proveedor Piper: voces neuronales que se ejecutan en el propio equipo.

Es la opción indicada si el ordenador del cuarto de control no tiene salida a
internet o si se quiere generar audio sin depender de un servicio externo.
Entrega WAV; :mod:`voceo.audio` lo convierte a MP3.

Instalación:
    pip install piper-tts
    # y descargar una voz en español, por ejemplo:
    #   https://huggingface.co/rhasspy/piper-voices/tree/main/es
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from voceo.errores import ErrorDeSintesis, ProveedorNoDisponible
from voceo.proveedores.base import Proveedor, Voz

#: Carpetas donde se buscan modelos `.onnx` si no se indica ninguno.
CARPETAS_MODELOS = [
    Path.home() / ".local" / "share" / "piper" / "voces",
    Path.home() / ".local" / "share" / "piper-voices",
    Path("modelos"),
]


def _escala_longitud(porcentaje: str) -> float:
    """«-10%» (más lento) se traduce en un `length_scale` mayor."""
    coincidencia = re.match(r"^([+-]?\d{1,3})%$", porcentaje.strip())
    if not coincidencia:
        return 1.0
    factor = 1.0 + int(coincidencia.group(1)) / 100
    factor = max(0.25, min(factor, 4.0))
    return round(1.0 / factor, 3)


def _ejecutable() -> str:
    for candidato in ("piper", "piper-tts"):
        ruta = shutil.which(candidato)
        if ruta:
            return ruta
    raise ProveedorNoDisponible(
        "No se encontró el programa «piper». Instálalo con:\n"
        "    pip install piper-tts"
    )


def modelos_encontrados() -> list[Path]:
    """Modelos `.onnx` disponibles en las carpetas habituales."""
    encontrados: list[Path] = []
    for carpeta in CARPETAS_MODELOS:
        if carpeta.is_dir():
            encontrados.extend(sorted(carpeta.glob("*.onnx")))
    return encontrados


class PiperTTS(Proveedor):
    nombre = "piper"
    formato = "wav"
    sin_conexion = True

    def _modelo(self) -> Path:
        """Ruta del modelo de voz: `voz` en la configuración o el primero encontrado."""
        if self.config.voz and self.config.voz.endswith(".onnx"):
            modelo = Path(self.config.voz).expanduser()
            if not modelo.is_file():
                raise ProveedorNoDisponible(f"No existe el modelo de voz: {modelo}")
            return modelo
        candidatos = modelos_encontrados()
        if not candidatos:
            raise ProveedorNoDisponible(
                "Piper necesita un modelo de voz (.onnx). Descarga uno en español de\n"
                "    https://huggingface.co/rhasspy/piper-voices/tree/main/es\n"
                "y apunta a él con  --voz /ruta/es_MX-voz.onnx  o colócalo en "
                f"{CARPETAS_MODELOS[0]}"
            )
        return candidatos[0]

    def verificar(self) -> None:
        _ejecutable()
        self._modelo()

    def sintetizar(self, texto: str, destino: Path) -> Path:
        programa = _ejecutable()
        modelo = self._modelo()
        destino = self._destino_con_formato(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)

        orden = [
            programa,
            "--model", str(modelo),
            "--output_file", str(destino),
            "--length_scale", str(_escala_longitud(self.config.velocidad)),
        ]
        try:
            resultado = subprocess.run(
                orden,
                input=texto.encode("utf-8"),
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise ErrorDeSintesis(f"No se pudo ejecutar piper: {exc}") from exc

        if resultado.returncode != 0 or not destino.exists():
            detalle = resultado.stderr.decode("utf-8", "replace").strip()
            destino.unlink(missing_ok=True)
            raise ErrorDeSintesis(f"piper falló: {detalle or resultado.returncode}")
        return destino

    def voces(self, idioma: str | None = "es") -> list[Voz]:
        encontradas = []
        for modelo in modelos_encontrados():
            if idioma and not modelo.name.lower().startswith(idioma.lower()):
                continue
            encontradas.append(
                Voz(id=str(modelo), nombre=modelo.stem, idioma=modelo.stem[:5])
            )
        return encontradas
