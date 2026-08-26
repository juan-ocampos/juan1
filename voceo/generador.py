"""Orquestación: de un texto escrito a un MP3 listo para la megafonía."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from voceo import audio, texto as modulo_texto
from voceo.config import Config
from voceo.errores import ErrorDeAudio, VoceoError
from voceo.proveedores import obtener


@dataclass
class Resultado:
    """Lo que se obtuvo al generar un aviso."""

    ruta: Path
    texto: str
    texto_original: str
    proveedor: str
    voz: str
    fragmentos: int = 1
    duracion: float | None = None
    avisos: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        partes = [str(self.ruta)]
        if self.duracion is not None:
            partes.append(f"{self.duracion:.1f} s")
        partes.append(f"{self.proveedor}/{self.voz}")
        return "  ·  ".join(partes)


def _metadatos(destino: Path, texto_final: str, config: Config) -> dict[str, str]:
    """Etiquetas ID3 para que el archivo se identifique en el reproductor."""
    comentario = texto_final if len(texto_final) <= 220 else texto_final[:217] + "..."
    return {
        "title": destino.stem.replace("-", " ").replace("_", " ").capitalize(),
        "artist": "Voceo",
        "album": "Avisos del centro comercial",
        "genre": "Speech",
        "date": date.today().isoformat(),
        "comment": comentario,
    }


def preparar_texto(entrada: str, config: Config) -> str:
    """Normaliza el texto y comprueba que quede algo que decir."""
    resultado = modulo_texto.normalizar(
        entrada,
        expandir=config.expandir_abreviaturas,
        marcadores=config.marcadores,
    )
    if not resultado:
        raise VoceoError("El texto está vacío: no hay nada que vocear.")
    return resultado


def generar(
    entrada: str,
    destino: Path,
    config: Config,
    *,
    sobrescribir: bool = True,
) -> Resultado:
    """Genera el MP3 del aviso `entrada` en `destino`.

    El texto se normaliza, se trocea si es muy largo, se sintetiza con el
    proveedor configurado y se monta con campanilla, silencios y repeticiones.
    """
    destino = Path(destino)
    if destino.suffix.lower() != ".mp3":
        destino = destino.with_suffix(".mp3")
    if destino.exists() and not sobrescribir:
        raise VoceoError(f"El archivo ya existe: {destino} (usa --sobrescribir)")

    texto_final = preparar_texto(entrada, config)
    fragmentos = modulo_texto.dividir(texto_final, config.max_caracteres)

    proveedor = obtener(config.proveedor, config)
    proveedor.verificar()

    avisos: list[str] = []
    destino.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="voceo-") as temporal:
        carpeta = Path(temporal)
        pistas = [
            proveedor.sintetizar(fragmento, carpeta / f"parte-{numero:02d}.tmp")
            for numero, fragmento in enumerate(fragmentos)
        ]

        hace_falta = audio.necesita_ffmpeg(config, len(pistas), proveedor.formato)
        if hace_falta and audio.ruta_ffmpeg():
            audio.masterizar(
                pistas,
                destino,
                config,
                metadatos=_metadatos(destino, texto_final, config),
            )
        elif hace_falta and proveedor.formato == "mp3" and len(pistas) == 1:
            # Sin ffmpeg se entrega la voz tal cual, avisando de lo que falta.
            omitido = []
            if config.campanilla:
                omitido.append("campanilla")
            if config.repetir > 1:
                omitido.append("repeticiones")
            if config.silencio_inicial or config.silencio_final:
                omitido.append("silencios")
            if config.normalizar_volumen:
                omitido.append("normalización de volumen")
            avisos.append(
                "ffmpeg no está instalado: se omitió "
                + ", ".join(omitido)
                + ". Instálalo (o `pip install imageio-ffmpeg`) para el aviso completo."
            )
            shutil.copyfile(pistas[0], destino)
        elif hace_falta:
            raise ErrorDeAudio(
                f"El proveedor «{proveedor.nombre}» entrega {proveedor.formato} y "
                "hace falta ffmpeg para convertirlo a MP3.\n"
                "Instálalo con `pip install imageio-ffmpeg` o desde el gestor de "
                "paquetes del sistema."
            )
        else:
            shutil.copyfile(pistas[0], destino)

    return Resultado(
        ruta=destino,
        texto=texto_final,
        texto_original=entrada.strip(),
        proveedor=proveedor.nombre,
        voz=config.voz,
        fragmentos=len(fragmentos),
        duracion=audio.duracion(destino),
        avisos=avisos,
    )
