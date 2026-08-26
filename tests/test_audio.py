"""Pruebas del montaje del audio."""

import wave

import pytest

from voceo import audio
from voceo.config import Config
from voceo.errores import ErrorDeAudio

from conftest import hace_falta_ffmpeg


def test_la_campanilla_es_un_wav_valido(tmp_path):
    ruta = audio.generar_campanilla(tmp_path / "camp.wav")
    with wave.open(str(ruta)) as archivo:
        assert archivo.getnchannels() == 1
        assert archivo.getsampwidth() == 2
        assert archivo.getframerate() == 44100
        duracion = archivo.getnframes() / archivo.getframerate()
    assert 1.0 < duracion < 2.0


def test_la_campanilla_no_satura(tmp_path):
    """Las muestras deben quedar dentro del rango de 16 bits sin recortarse."""
    ruta = audio.generar_campanilla(tmp_path / "camp.wav", volumen=0.45)
    with wave.open(str(ruta)) as archivo:
        datos = archivo.readframes(archivo.getnframes())
    maximo = max(
        abs(int.from_bytes(datos[i : i + 2], "little", signed=True))
        for i in range(0, len(datos), 2)
    )
    assert 0 < maximo < 32767


def test_campanilla_del_usuario_inexistente(tmp_path):
    config = Config(campanilla_archivo=tmp_path / "no-existe.wav")
    with pytest.raises(ErrorDeAudio, match="campanilla"):
        audio.campanilla_para(config)


def test_campanilla_del_usuario_se_respeta(tmp_path):
    propia = audio.generar_campanilla(tmp_path / "propia.wav")
    config = Config(campanilla_archivo=propia)
    assert audio.campanilla_para(config) == propia


@pytest.mark.parametrize(
    "config,esperado",
    [
        (Config(campanilla=True), True),
        (Config(campanilla=False, normalizar_volumen=False,
                silencio_inicial=0, silencio_final=0), False),
        (Config(campanilla=False, normalizar_volumen=False,
                silencio_inicial=0, silencio_final=0, repetir=2), True),
    ],
)
def test_cuando_hace_falta_ffmpeg(config, esperado):
    assert audio.necesita_ffmpeg(config, 1, "mp3") is esperado


def test_varios_fragmentos_siempre_necesitan_ffmpeg():
    simple = Config(campanilla=False, normalizar_volumen=False,
                    silencio_inicial=0, silencio_final=0)
    assert audio.necesita_ffmpeg(simple, 2, "mp3") is True


def test_un_wav_siempre_necesita_ffmpeg():
    simple = Config(campanilla=False, normalizar_volumen=False,
                    silencio_inicial=0, silencio_final=0)
    assert audio.necesita_ffmpeg(simple, 1, "wav") is True


def test_masterizar_sin_pistas(tmp_path):
    with pytest.raises(ErrorDeAudio):
        audio.masterizar([], tmp_path / "x.mp3", Config())


@hace_falta_ffmpeg
def test_masterizar_arma_el_aviso_completo(tmp_path):
    voz = audio.generar_campanilla(tmp_path / "voz.wav", notas=((220.0, 2.0),))
    config = Config(
        campanilla=True,
        repetir=2,
        pausa_repeticion=1.0,
        silencio_inicial=0.5,
        silencio_final=1.0,
        normalizar_volumen=False,
    )
    salida = audio.masterizar([voz], tmp_path / "aviso.mp3", config)
    assert salida.exists() and salida.stat().st_size > 0
    # 0.5 + 1.35 (campanilla) + 0.35 + 2 + 1 + 2 + 1 = 8.2 s
    assert 7.8 < audio.duracion(salida) < 8.7


@hace_falta_ffmpeg
def test_masterizar_une_varios_fragmentos(tmp_path):
    uno = audio.generar_campanilla(tmp_path / "1.wav", notas=((220.0, 1.0),))
    dos = audio.generar_campanilla(tmp_path / "2.wav", notas=((330.0, 1.0),))
    config = Config(campanilla=False, normalizar_volumen=False,
                    silencio_inicial=0, silencio_final=0)
    salida = audio.masterizar([uno, dos], tmp_path / "union.mp3", config)
    assert 1.8 < audio.duracion(salida) < 2.4


@hace_falta_ffmpeg
def test_masterizar_normaliza_el_volumen(tmp_path):
    voz = audio.generar_campanilla(tmp_path / "voz.wav", notas=((220.0, 1.5),), volumen=0.02)
    config = Config(campanilla=False, silencio_inicial=0, silencio_final=0,
                    normalizar_volumen=True)
    salida = audio.masterizar([voz], tmp_path / "normalizado.mp3", config)
    assert salida.stat().st_size > 0


@hace_falta_ffmpeg
def test_convertir_a_mp3(tmp_path):
    origen = audio.generar_campanilla(tmp_path / "origen.wav")
    salida = audio.convertir_a_mp3(origen, tmp_path / "salida.mp3", Config())
    assert salida.exists()
    assert audio.duracion(salida) > 1.0
