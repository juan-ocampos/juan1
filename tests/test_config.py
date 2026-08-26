"""Pruebas de la carga de configuración."""

import pytest

from voceo import config as modulo
from voceo.config import Config
from voceo.errores import ErrorDeConfiguracion


def _escribir(tmp_path, contenido):
    ruta = tmp_path / "voceo.toml"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_valores_por_defecto():
    config = Config()
    assert config.proveedor == "edge"
    assert config.voz.startswith("es-")
    assert config.canales == 1


def test_carga_desde_toml(tmp_path):
    ruta = _escribir(tmp_path, 'voz = "es-ES-ElviraNeural"\nrepetir = 3\n')
    config = modulo.cargar(ruta)
    assert config.voz == "es-ES-ElviraNeural"
    assert config.repetir == 3


def test_el_perfil_manda_sobre_el_bloque_general(tmp_path):
    ruta = _escribir(
        tmp_path,
        'velocidad = "-5%"\nrepetir = 1\n\n[perfiles.emergencia]\nvelocidad = "-15%"\nrepetir = 2\n',
    )
    config = modulo.cargar(ruta, "emergencia")
    assert config.velocidad == "-15%"
    assert config.repetir == 2


def test_perfil_inexistente_avisa_de_los_disponibles(tmp_path):
    ruta = _escribir(tmp_path, "[perfiles.nocturno]\nrepetir = 2\n")
    with pytest.raises(ErrorDeConfiguracion, match="nocturno"):
        modulo.cargar(ruta, "fiesta")


def test_ajuste_desconocido_en_el_archivo(tmp_path):
    ruta = _escribir(tmp_path, 'vozz = "x"\n')
    with pytest.raises(ErrorDeConfiguracion, match="vozz"):
        modulo.cargar(ruta)


def test_archivo_inexistente(tmp_path):
    with pytest.raises(ErrorDeConfiguracion):
        modulo.cargar(tmp_path / "no-existe.toml")


def test_toml_invalido(tmp_path):
    ruta = _escribir(tmp_path, "esto no es toml =")
    with pytest.raises(ErrorDeConfiguracion, match="TOML"):
        modulo.cargar(ruta)


def test_con_ignora_los_valores_nulos():
    config = Config(repetir=2)
    assert config.con(repetir=None).repetir == 2
    assert config.con(repetir=5).repetir == 5


def test_con_rechaza_ajustes_desconocidos():
    with pytest.raises(ErrorDeConfiguracion):
        Config().con(inventado=1)


@pytest.mark.parametrize(
    "valor,esperado",
    [("si", True), ("sí", True), ("1", True), ("no", False), ("false", False), ("", False)],
)
def test_interpreta_si_y_no(valor, esperado):
    assert modulo.a_bool(valor) is esperado


def test_valor_no_booleano_da_error():
    with pytest.raises(ErrorDeConfiguracion):
        modulo.aplicar(Config(), {"campanilla": "quizá"}, "prueba")


def test_aplicar_convierte_los_tipos():
    config = modulo.aplicar(Config(), {"repetir": "3", "silencio_final": "1.5"}, "x")
    assert config.repetir == 3
    assert config.silencio_final == 1.5


def test_clave_api_falta(monkeypatch):
    monkeypatch.delenv("CLAVE_DE_PRUEBA", raising=False)
    with pytest.raises(ErrorDeConfiguracion, match="CLAVE_DE_PRUEBA"):
        modulo.clave_api("CLAVE_DE_PRUEBA", "prueba")


def test_clave_api_presente(monkeypatch):
    monkeypatch.setenv("CLAVE_DE_PRUEBA", "abc")
    assert modulo.clave_api("CLAVE_DE_PRUEBA", "prueba") == "abc"


@pytest.mark.parametrize(
    "entrada,esperado",
    [("-10%", "-10%"), ("-10", "-10%"), ("10", "+10%"), ("+5%", "+5%"), ("", "+0%")],
)
def test_normaliza_los_porcentajes(entrada, esperado):
    assert modulo.normalizar_porcentaje(entrada) == esperado


@pytest.mark.parametrize(
    "entrada,esperado",
    [("+5Hz", "+5Hz"), ("-3hz", "-3Hz"), ("5", "+5Hz"), ("", "+0Hz")],
)
def test_normaliza_los_hercios(entrada, esperado):
    assert modulo.normalizar_hercios(entrada) == esperado


def test_la_config_guarda_los_valores_normalizados():
    config = Config(velocidad="-10", volumen="5%", tono="-3hz")
    assert (config.velocidad, config.volumen, config.tono) == ("-10%", "+5%", "-3Hz")


def test_un_valor_raro_se_deja_tal_cual_para_que_el_proveedor_lo_explique():
    assert Config(velocidad="rapido").velocidad == "rapido"
