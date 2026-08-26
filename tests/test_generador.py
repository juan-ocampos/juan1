"""Pruebas del proceso completo: texto -> MP3."""

import pytest

from voceo import audio, generador
from voceo.errores import ErrorDeAudio, VoceoError

from conftest import hace_falta_ffmpeg


def test_genera_el_mp3_y_devuelve_el_resumen(proveedor_falso, config_basica, tmp_path):
    resultado = generador.generar("Hola centro comercial.", tmp_path / "aviso.mp3", config_basica)
    assert resultado.ruta.exists()
    assert resultado.ruta.suffix == ".mp3"
    assert resultado.proveedor == "falso-mp3"
    assert "aviso.mp3" in resultado.resumen()


def test_pone_la_extension_mp3_si_falta(proveedor_falso, config_basica, tmp_path):
    resultado = generador.generar("Hola.", tmp_path / "aviso", config_basica)
    assert resultado.ruta.name == "aviso.mp3"


def test_el_texto_llega_normalizado_al_proveedor(proveedor_falso, config_basica, tmp_path):
    generador.generar("El Sr. López al mód. 2", tmp_path / "a.mp3", config_basica)
    assert proveedor_falso.recibidos == ["El señor López al módulo 2"]


def test_texto_vacio(proveedor_falso, config_basica, tmp_path):
    with pytest.raises(VoceoError, match="vacío"):
        generador.generar("   ", tmp_path / "a.mp3", config_basica)


def test_no_sobrescribe_si_no_se_pide(proveedor_falso, config_basica, tmp_path):
    destino = tmp_path / "a.mp3"
    generador.generar("Hola.", destino, config_basica)
    with pytest.raises(VoceoError, match="ya existe"):
        generador.generar("Hola.", destino, config_basica, sobrescribir=False)


def test_avisa_cuando_falta_ffmpeg(proveedor_falso, config_basica, tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "ruta_ffmpeg", lambda: None)
    config = config_basica.con(campanilla=True, normalizar_volumen=True)
    resultado = generador.generar("Hola.", tmp_path / "a.mp3", config)
    assert resultado.ruta.exists()
    assert any("ffmpeg" in aviso for aviso in resultado.avisos)
    assert any("campanilla" in aviso for aviso in resultado.avisos)


def test_sin_ffmpeg_y_con_wav_es_un_error(proveedor_falso, config_basica, tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "ruta_ffmpeg", lambda: None)
    config = config_basica.con(proveedor="falso")  # entrega WAV
    with pytest.raises(ErrorDeAudio, match="ffmpeg"):
        generador.generar("Hola.", tmp_path / "a.mp3", config)


@hace_falta_ffmpeg
def test_trocea_los_textos_largos(proveedor_falso, config_basica, tmp_path):
    largo = "Aviso de prueba. " * 30
    # El proveedor «falso» entrega WAV de verdad, así que los trozos se pueden unir.
    config = config_basica.con(proveedor="falso", max_caracteres=100)
    resultado = generador.generar(largo, tmp_path / "largo.mp3", config)
    assert resultado.fragmentos > 1
    assert len(proveedor_falso.recibidos) == resultado.fragmentos


@hace_falta_ffmpeg
def test_aviso_completo_con_campanilla_y_repeticion(proveedor_falso, tmp_path):
    from voceo.config import Config

    config = Config(
        proveedor="falso",
        campanilla=True,
        repetir=2,
        pausa_repeticion=1.0,
        silencio_inicial=0.5,
        silencio_final=0.5,
        normalizar_volumen=False,
    )
    resultado = generador.generar("Atención.", tmp_path / "completo.mp3", config)
    assert resultado.duracion is not None
    # Es bastante más largo que la voz sola gracias a campanilla y repetición.
    assert resultado.duracion > 4.0


@hace_falta_ffmpeg
def test_guarda_las_etiquetas_id3(proveedor_falso, tmp_path):
    from voceo.config import Config

    config = Config(proveedor="falso", campanilla=False, normalizar_volumen=False,
                    silencio_inicial=0, silencio_final=0)
    resultado = generador.generar("Aviso de prueba.", tmp_path / "cierre-noche.mp3", config)
    contenido = resultado.ruta.read_bytes()
    assert b"Voceo" in contenido
    assert "Cierre noche".encode("utf-16-le") in contenido or b"Cierre noche" in contenido
