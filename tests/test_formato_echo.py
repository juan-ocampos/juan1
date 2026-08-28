"""Pruebas del formato exigido por los equipos de voceo de estacionamiento.

La especificación del proyecto Echo pide MP3 mono de 44.100 Hz a 96 kbit/s CBR
que empiece directamente en el audio: sin etiqueta ID3 y sin cabecera Xing.
"""

from pathlib import Path

import pytest

from voceo import audio, generador
from voceo import config as modulo_config
from voceo.config import Config
from voceo.errores import ErrorDeAudio

from conftest import hace_falta_ffmpeg


# --- el perfil integrado -------------------------------------------------
def test_el_perfil_echo_viene_de_fabrica():
    config = modulo_config.cargar(None, "echo")
    assert config.bitrate == "96k"
    assert config.frecuencia == 44100
    assert config.canales == 1
    assert config.id3 is False
    assert config.xing is False
    assert config.compresor is True


def test_el_perfil_echo_aparece_en_la_lista():
    assert "echo" in modulo_config.perfiles_disponibles()


def test_el_perfil_del_usuario_gana_al_integrado(tmp_path):
    ruta = tmp_path / "voceo.toml"
    ruta.write_text('[perfiles.echo]\nbitrate = "128k"\n', encoding="utf-8")
    assert modulo_config.cargar(ruta, "echo").bitrate == "128k"


# --- el validador --------------------------------------------------------
def _mp3_falso(tmp_path, contenido: bytes) -> Path:
    ruta = tmp_path / "prueba.mp3"
    ruta.write_bytes(contenido)
    return ruta


def test_rechaza_un_archivo_que_empieza_con_id3(tmp_path):
    revision = audio.comprobar_mp3(_mp3_falso(tmp_path, b"ID3\x04\x00" + b"\x00" * 64))
    assert not revision.valido
    assert "ID3" in revision.problemas[0]


def test_acepta_un_sincronismo_valido(tmp_path):
    revision = audio.comprobar_mp3(_mp3_falso(tmp_path, b"\xff\xfb\x70\xc4" + b"\x00" * 64))
    assert revision.valido


def test_rechaza_un_primer_byte_que_no_es_sincronismo(tmp_path):
    revision = audio.comprobar_mp3(_mp3_falso(tmp_path, b"\x00\xfb\x70\xc4" + b"\x00" * 64))
    assert not revision.valido
    assert "trama MPEG" in revision.problemas[0]


def test_rechaza_un_sincronismo_incompleto(tmp_path):
    # 0xFF seguido de algo que no completa el patrón de sincronismo.
    revision = audio.comprobar_mp3(_mp3_falso(tmp_path, b"\xff\x0b\x70\xc4" + b"\x00" * 64))
    assert not revision.valido


def test_rechaza_la_cabecera_xing(tmp_path):
    # MPEG-1 mono: la etiqueta va en el byte 21 (4 + 17 de información lateral).
    trama = bytearray(b"\xff\xfb\x70\xc4" + b"\x00" * 320)
    trama[21:25] = b"Xing"
    revision = audio.comprobar_mp3(_mp3_falso(tmp_path, bytes(trama)))
    assert not revision.valido
    assert "Xing" in revision.problemas[0]


def test_el_texto_de_lame_en_los_datos_auxiliares_no_es_una_cabecera(tmp_path):
    """LAME escribe su versión dentro de la trama; eso no invalida el archivo."""
    trama = bytearray(b"\xff\xfb\x70\xc4" + b"\x00" * 320)
    trama[40:49] = b"LAME3.100"
    assert audio.comprobar_mp3(_mp3_falso(tmp_path, bytes(trama))).valido


def test_archivo_inexistente(tmp_path):
    revision = audio.comprobar_mp3(tmp_path / "no-existe.mp3")
    assert not revision.valido


def test_archivo_truncado(tmp_path):
    revision = audio.comprobar_mp3(_mp3_falso(tmp_path, b"\xff"))
    assert not revision.valido


@pytest.mark.parametrize(
    "entrada,esperado",
    [("96k", 96), ("96", 96), ("160k", 160), ("128000", 128), ("raro", None)],
)
def test_lectura_del_bitrate(entrada, esperado):
    assert audio._kbps_de(entrada) == esperado


# --- la generación completa ---------------------------------------------
@hace_falta_ffmpeg
def test_el_perfil_echo_produce_un_mp3_que_empieza_en_el_audio(proveedor_falso, tmp_path):
    config = modulo_config.cargar(None, "echo").con(
        proveedor="falso", salida=tmp_path, campanilla=False
    )
    resultado = generador.generar("Aviso de estacionamiento de prueba.",
                                  tmp_path / "aviso.mp3", config)
    datos = resultado.ruta.read_bytes()

    # La comprobación literal de la especificación.
    assert datos[:3] != b"ID3"
    assert datos[0] == 0xFF
    assert datos[1] & 0xE0 == 0xE0

    revision = audio.comprobar_mp3(resultado.ruta, kbps_esperado=96)
    assert revision.valido, revision.problemas


@hace_falta_ffmpeg
def test_el_perfil_echo_da_96_kbits_constantes(proveedor_falso, tmp_path):
    config = modulo_config.cargar(None, "echo").con(
        proveedor="falso", salida=tmp_path, campanilla=False
    )
    resultado = generador.generar("Aviso largo de prueba para medir el bitrate.",
                                  tmp_path / "aviso.mp3", config)
    # La regla de bulto de la especificación: unos 12 KB por segundo.
    kb_por_segundo = resultado.ruta.stat().st_size / 1024 / resultado.duracion
    assert 10.5 < kb_por_segundo < 13.5


@hace_falta_ffmpeg
def test_por_defecto_se_siguen_escribiendo_las_etiquetas(proveedor_falso, tmp_path):
    """El comportamiento normal no cambia: sigue llevando ID3."""
    config = Config(proveedor="falso", campanilla=False, normalizar_volumen=False,
                    silencio_inicial=0, silencio_final=0)
    resultado = generador.generar("Hola", tmp_path / "normal.mp3", config)
    assert resultado.ruta.read_bytes()[:3] == b"ID3"


@hace_falta_ffmpeg
def test_el_compresor_se_aplica(proveedor_falso, tmp_path, monkeypatch):
    ordenes: list[list[str]] = []
    original = audio.subprocess.run

    def espia(orden, *args, **extra):
        ordenes.append(orden)
        return original(orden, *args, **extra)

    monkeypatch.setattr(audio.subprocess, "run", espia)
    config = Config(proveedor="falso", compresor=True, campanilla=False)
    generador.generar("Hola", tmp_path / "a.mp3", config)
    filtros = " ".join(" ".join(o) for o in ordenes)
    assert "acompressor" in filtros
    assert "alimiter" in filtros


@hace_falta_ffmpeg
def test_un_formato_estricto_que_no_cuadra_se_detecta(proveedor_falso, tmp_path, monkeypatch):
    """Si ffmpeg no hiciera lo pedido, el generador debe darse cuenta."""
    config = modulo_config.cargar(None, "echo").con(proveedor="falso", campanilla=False)

    # Se simula un ffmpeg que escribe un archivo con ID3 por delante.
    original = audio.subprocess.run

    def sucio(orden, *args, **extra):
        resultado = original(orden, *args, **extra)
        destino = Path(orden[-1])
        if destino.suffix == ".mp3" and destino.exists():
            destino.write_bytes(b"ID3\x04\x00" + destino.read_bytes())
        return resultado

    monkeypatch.setattr(audio.subprocess, "run", sucio)
    with pytest.raises(ErrorDeAudio, match="ID3"):
        generador.generar("Hola", tmp_path / "a.mp3", config)


def test_sin_id3_siempre_hace_falta_ffmpeg():
    simple = Config(campanilla=False, normalizar_volumen=False,
                    silencio_inicial=0, silencio_final=0, id3=False)
    assert audio.necesita_ffmpeg(simple, 1, "mp3") is True


def test_con_compresor_siempre_hace_falta_ffmpeg():
    simple = Config(campanilla=False, normalizar_volumen=False,
                    silencio_inicial=0, silencio_final=0, compresor=True)
    assert audio.necesita_ffmpeg(simple, 1, "mp3") is True
