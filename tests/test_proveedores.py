"""Pruebas de los proveedores de voz (sin llamar a ningún servicio)."""

import pytest

from voceo import proveedores
from voceo.config import Config
from voceo.errores import ErrorDeConfiguracion, ProveedorNoDisponible
from voceo.proveedores.base import Proveedor
from voceo.proveedores.edge import EdgeTTS
from voceo.proveedores.elevenlabs import _factor_velocidad as factor_eleven
from voceo.proveedores.openai_tts import _factor_velocidad as factor_openai
from voceo.proveedores.piper import _escala_longitud


def test_todos_los_proveedores_estan_descritos():
    assert set(proveedores.nombres()) == set(proveedores.DESCRIPCIONES)


def test_obtener_devuelve_una_instancia():
    assert isinstance(proveedores.obtener("edge", Config()), EdgeTTS)


def test_proveedor_desconocido():
    with pytest.raises(ProveedorNoDisponible, match="edge"):
        proveedores.obtener("inventado", Config())


def test_cada_proveedor_declara_su_formato():
    for nombre in proveedores.nombres():
        proveedor = proveedores.obtener(nombre, Config())
        assert proveedor.nombre == nombre
        assert proveedor.formato in {"mp3", "wav"}


def test_el_destino_se_ajusta_al_formato(tmp_path):
    class Wav(Proveedor):
        nombre, formato = "x", "wav"

        def verificar(self):
            return None

        def sintetizar(self, texto, destino):
            return destino

    destino = Wav(Config())._destino_con_formato(tmp_path / "a.mp3")
    assert destino.name == "a.wav"


def test_edge_valida_la_velocidad():
    with pytest.raises(ProveedorNoDisponible, match="velocidad"):
        EdgeTTS(Config(velocidad="rapido")).verificar()


def test_edge_valida_el_tono():
    with pytest.raises(ProveedorNoDisponible, match="tono"):
        EdgeTTS(Config(tono="grave")).verificar()


def test_edge_acepta_los_valores_normalizados():
    EdgeTTS(Config(velocidad="-10", volumen="5", tono="-3")).verificar()


@pytest.mark.parametrize(
    "entrada,esperado",
    [("+0%", 1.0), ("-10%", 0.9), ("+50%", 1.5), ("raro", 1.0)],
)
def test_factor_de_velocidad_de_openai(entrada, esperado):
    assert factor_openai(entrada) == pytest.approx(esperado)


def test_elevenlabs_recorta_la_velocidad_a_su_rango():
    assert factor_eleven("-90%") == pytest.approx(0.7)
    assert factor_eleven("+90%") == pytest.approx(1.2)


def test_piper_invierte_la_velocidad():
    # Más lento (-50%) significa alargar la duración: length_scale = 2
    assert _escala_longitud("-50%") == pytest.approx(2.0)
    assert _escala_longitud("+0%") == pytest.approx(1.0)


def test_openai_pide_la_clave(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    openai = pytest.importorskip("openai")  # solo si está instalado el SDK
    with pytest.raises(ErrorDeConfiguracion, match="OPENAI_API_KEY"):
        proveedores.obtener("openai", Config()).verificar()


def test_piper_sin_modelo_explica_como_conseguirlo(monkeypatch, tmp_path):
    from voceo.proveedores import piper

    monkeypatch.setattr(piper, "_ejecutable", lambda: "piper")
    monkeypatch.setattr(piper, "CARPETAS_MODELOS", [tmp_path / "vacía"])
    with pytest.raises(ProveedorNoDisponible, match="onnx"):
        piper.PiperTTS(Config(voz="es-MX-Dalia")).verificar()
