"""Producción del audio final: campanilla, silencios, repeticiones y MP3.

La síntesis de voz la hace el proveedor; aquí se convierte esa voz «desnuda»
en un aviso listo para la megafonía: campanilla de atención, un silencio antes
y después, el mensaje repetido las veces que haga falta y el volumen
normalizado para que todos los avisos suenen igual de fuertes.

Todo esto se apoya en ffmpeg. Si ffmpeg no está instalado, el programa sigue
funcionando para el caso básico (un único MP3 sin adornos) y avisa de lo que
se está omitiendo.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from voceo.config import Config
from voceo.errores import ErrorDeAudio

#: Notas de la campanilla por defecto: un «din-don» descendente.
CAMPANILLA_POR_DEFECTO: tuple[tuple[float, float], ...] = (
    (880.00, 0.40),   # la5
    (659.25, 0.95),   # mi5
)

#: Dónde se guarda la campanilla generada para no recrearla en cada aviso.
CACHE = Path.home() / ".cache" / "voceo"


def ruta_ffmpeg() -> str | None:
    """Ruta del ejecutable de ffmpeg, o `None` si no está instalado.

    Si no hay ffmpeg en el sistema se usa el que trae el paquete opcional
    `imageio-ffmpeg`, que se instala con pip y evita tener que instalar ffmpeg
    a mano (útil sobre todo en Windows).
    """
    del_sistema = shutil.which("ffmpeg")
    if del_sistema:
        return del_sistema
    try:
        import imageio_ffmpeg  # noqa: PLC0415

        ruta = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    return ruta if ruta and Path(ruta).exists() else None


def ruta_ffprobe() -> str | None:
    return shutil.which("ffprobe")


def exigir_ffmpeg(motivo: str) -> str:
    programa = ruta_ffmpeg()
    if not programa:
        raise ErrorDeAudio(
            f"Hace falta ffmpeg para {motivo}.\n"
            "  Debian/Ubuntu:  sudo apt install ffmpeg\n"
            "  macOS:          brew install ffmpeg\n"
            "  Windows:        winget install Gyan.FFmpeg"
        )
    return programa


def generar_campanilla(
    destino: Path,
    notas: tuple[tuple[float, float], ...] = CAMPANILLA_POR_DEFECTO,
    *,
    frecuencia: int = 44100,
    volumen: float = 0.45,
) -> Path:
    """Sintetiza un «din-don» de megafonía y lo guarda como WAV.

    Se genera con la biblioteca estándar (nada de dependencias ni de archivos
    binarios en el repositorio): una senoidal con dos armónicos y una envolvente
    de decaimiento, que es justo el timbre de una campana.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    muestras = bytearray()
    for hercios, duracion in notas:
        total = int(frecuencia * duracion)
        for indice in range(total):
            t = indice / frecuencia
            decaimiento = math.exp(-3.2 * t / duracion)
            ataque = min(1.0, t / 0.005)  # 5 ms de ataque: evita el «clic»
            onda = (
                math.sin(2 * math.pi * hercios * t)
                + 0.35 * math.sin(2 * math.pi * 2 * hercios * t)
                + 0.12 * math.sin(2 * math.pi * 3 * hercios * t)
            ) / 1.47
            valor = max(-1.0, min(1.0, onda * decaimiento * ataque * volumen))
            muestras += struct.pack("<h", int(valor * 32767))

    with wave.open(str(destino), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia)
        archivo.writeframes(bytes(muestras))
    return destino


def campanilla_para(config: Config) -> Path:
    """Devuelve la campanilla a usar: la del usuario o la generada en caché."""
    if config.campanilla_archivo:
        ruta = Path(config.campanilla_archivo).expanduser()
        if not ruta.is_file():
            raise ErrorDeAudio(f"No existe el archivo de campanilla: {ruta}")
        return ruta
    ruta = CACHE / f"campanilla-{config.frecuencia}.wav"
    if not ruta.is_file():
        generar_campanilla(ruta, frecuencia=config.frecuencia)
    return ruta


def duracion(ruta: Path) -> float | None:
    """Duración en segundos del archivo, o `None` si no se puede averiguar."""
    programa = ruta_ffprobe()
    if programa:
        orden = [
            programa, "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(ruta),
        ]
        resultado = subprocess.run(orden, capture_output=True, check=False)
        if resultado.returncode == 0:
            try:
                datos = json.loads(resultado.stdout.decode("utf-8", "replace"))
                return round(float(datos["format"]["duration"]), 2)
            except (ValueError, KeyError):
                pass

    # Sin ffprobe: se decodifica con ffmpeg y se lee el tiempo final.
    programa = ruta_ffmpeg()
    if not programa:
        return None
    resultado = subprocess.run(
        [programa, "-hide_banner", "-i", str(ruta), "-f", "null", "-"],
        capture_output=True,
        check=False,
    )
    marcas = re.findall(
        r"time=(\d+):(\d{2}):(\d{2})\.(\d{2})",
        resultado.stderr.decode("utf-8", "replace"),
    )
    if not marcas:
        return None
    horas, minutos, segundos, centesimas = marcas[-1]
    return round(
        int(horas) * 3600 + int(minutos) * 60 + int(segundos) + int(centesimas) / 100, 2
    )


def _disposicion(canales: int) -> str:
    return "mono" if canales <= 1 else "stereo"


def _silencio(etiqueta: str, segundos: float, config: Config) -> str:
    """Filtro que genera un tramo de silencio."""
    return (
        f"anullsrc=r={config.frecuencia}:cl={_disposicion(config.canales)},"
        f"atrim=duration={segundos:.3f},asetpts=N/SR/TB[{etiqueta}]"
    )


def _formato(config: Config) -> str:
    return (
        f"aformat=sample_fmts=fltp:sample_rates={config.frecuencia}:"
        f"channel_layouts={_disposicion(config.canales)}"
    )


def necesita_ffmpeg(config: Config, fragmentos: int, formato_origen: str) -> bool:
    """¿La configuración pedida requiere pasar por ffmpeg?"""
    return (
        fragmentos > 1
        or formato_origen != "mp3"
        or config.campanilla
        or config.repetir > 1
        or config.silencio_inicial > 0
        or config.silencio_final > 0
        or config.normalizar_volumen
    )


def masterizar(
    pistas: list[Path],
    destino: Path,
    config: Config,
    *,
    metadatos: dict[str, str] | None = None,
) -> Path:
    """Une las pistas de voz con la campanilla y los silencios, y escribe el MP3.

    Args:
        pistas: fragmentos de voz en el orden en que deben sonar.
        destino: archivo MP3 a escribir.
        config: ajustes de producción.
        metadatos: etiquetas ID3 (`title`, `comment`, …).
    """
    if not pistas:
        raise ErrorDeAudio("No hay ninguna pista de voz que procesar.")
    programa = exigir_ffmpeg("montar el aviso (campanilla, silencios, repeticiones)")
    destino.parent.mkdir(parents=True, exist_ok=True)

    entradas: list[str] = []
    filtros: list[str] = []
    secuencia: list[str] = []

    # 1. Las pistas de voz se normalizan de formato y se encadenan.
    for indice, pista in enumerate(pistas):
        entradas += ["-i", str(pista)]
        filtros.append(f"[{indice}:a]{_formato(config)}[voz{indice}]")
    if len(pistas) == 1:
        etiqueta_voz = "voz0"
    else:
        cadena = "".join(f"[voz{i}]" for i in range(len(pistas)))
        filtros.append(f"{cadena}concat=n={len(pistas)}:v=0:a=1[voz]")
        etiqueta_voz = "voz"

    # 2. La voz completa se duplica tantas veces como repeticiones se pidan.
    repeticiones = max(1, config.repetir)
    if repeticiones > 1:
        salidas = "".join(f"[rep{i}]" for i in range(repeticiones))
        filtros.append(f"[{etiqueta_voz}]asplit={repeticiones}{salidas}")
        etiquetas_repeticion = [f"rep{i}" for i in range(repeticiones)]
    else:
        etiquetas_repeticion = [etiqueta_voz]

    # 3. Se arma la secuencia final: silencio, campanilla, mensaje(s), silencio.
    if config.silencio_inicial > 0:
        filtros.append(_silencio("sil_ini", config.silencio_inicial, config))
        secuencia.append("sil_ini")

    if config.campanilla:
        indice_campanilla = len(pistas)
        entradas += ["-i", str(campanilla_para(config))]
        filtros.append(f"[{indice_campanilla}:a]{_formato(config)}[camp]")
        secuencia.append("camp")
        filtros.append(_silencio("sil_camp", 0.35, config))
        secuencia.append("sil_camp")

    for numero, etiqueta in enumerate(etiquetas_repeticion):
        if numero > 0 and config.pausa_repeticion > 0:
            nombre = f"sil_rep{numero}"
            filtros.append(_silencio(nombre, config.pausa_repeticion, config))
            secuencia.append(nombre)
        secuencia.append(etiqueta)

    if config.silencio_final > 0:
        filtros.append(_silencio("sil_fin", config.silencio_final, config))
        secuencia.append("sil_fin")

    cadena_final = "".join(f"[{e}]" for e in secuencia)
    filtros.append(f"{cadena_final}concat=n={len(secuencia)}:v=0:a=1[mezcla]")

    if config.normalizar_volumen:
        # loudnorm deja todos los avisos a la misma sonoridad percibida.
        filtros.append(
            f"[mezcla]loudnorm=I=-16:TP=-1.5:LRA=11,aresample={config.frecuencia}[salida]"
        )
        etiqueta_salida = "salida"
    else:
        etiqueta_salida = "mezcla"

    orden = [programa, "-y", "-hide_banner", "-loglevel", "error"]
    orden += entradas
    orden += ["-filter_complex", ";".join(filtros), "-map", f"[{etiqueta_salida}]"]
    for clave, valor in (metadatos or {}).items():
        orden += ["-metadata", f"{clave}={valor}"]
    orden += [
        "-c:a", "libmp3lame",
        "-b:a", config.bitrate,
        "-ar", str(config.frecuencia),
        "-ac", str(config.canales),
        str(destino),
    ]

    resultado = subprocess.run(orden, capture_output=True, check=False)
    if resultado.returncode != 0:
        detalle = resultado.stderr.decode("utf-8", "replace").strip()
        raise ErrorDeAudio(f"ffmpeg falló al montar el aviso:\n{detalle}")
    return destino


def convertir_a_mp3(origen: Path, destino: Path, config: Config) -> Path:
    """Reempaqueta un audio como MP3 sin más procesamiento."""
    programa = exigir_ffmpeg("convertir el audio a MP3")
    destino.parent.mkdir(parents=True, exist_ok=True)
    orden = [
        programa, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(origen),
        "-c:a", "libmp3lame", "-b:a", config.bitrate,
        "-ar", str(config.frecuencia), "-ac", str(config.canales),
        str(destino),
    ]
    resultado = subprocess.run(orden, capture_output=True, check=False)
    if resultado.returncode != 0:
        detalle = resultado.stderr.decode("utf-8", "replace").strip()
        raise ErrorDeAudio(f"ffmpeg no pudo convertir a MP3:\n{detalle}")
    return destino
