"""Pruebas de los proveedores de voz (sin llamar a ningún servicio)."""

import pytest

from voceo import proveedores
from voceo.config import Config
from voceo.errores import (
    ErrorDeConfiguracion,
    ErrorDeSintesis,
    ProveedorNoDisponible,
)
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


# --- el 403 del servicio de Microsoft ------------------------------------
from voceo.proveedores import edge as modulo_edge  # noqa: E402


def test_detecta_el_403_por_el_atributo_status():
    fallo = Exception("algo")
    fallo.status = 403
    assert modulo_edge._es_403(fallo)


def test_detecta_el_403_en_el_texto():
    assert modulo_edge._es_403(Exception("403, message='Invalid response status'"))


def test_no_confunde_otros_numeros_con_un_403():
    assert not modulo_edge._es_403(Exception("se recibieron 4030 bytes"))
    assert not modulo_edge._es_403(Exception("500, error interno"))


def test_el_mensaje_del_403_explica_como_arreglarlo():
    mensaje = modulo_edge._mensaje_de_fallo("falló", Exception("403, Forbidden"))
    assert "pip install -U" in mensaje
    assert "reloj" in mensaje


def test_los_demas_fallos_no_llevan_la_receta():
    mensaje = modulo_edge._mensaje_de_fallo("falló", Exception("sin conexión"))
    assert "pip install" not in mensaje


def test_una_version_antigua_de_edge_tts_se_detecta(monkeypatch):
    monkeypatch.setattr(modulo_edge, "_version_instalada", lambda: "7.2.8")
    with pytest.raises(ProveedorNoDisponible, match="403"):
        EdgeTTS(Config()).verificar()


def test_la_version_vigente_pasa_la_comprobacion(monkeypatch):
    monkeypatch.setattr(modulo_edge, "_version_instalada", lambda: modulo_edge.VERSION_MINIMA)
    EdgeTTS(Config()).verificar()


def test_una_version_mas_nueva_tambien_pasa(monkeypatch):
    monkeypatch.setattr(modulo_edge, "_version_instalada", lambda: "8.0.0")
    EdgeTTS(Config()).verificar()


def test_el_403_al_sintetizar_llega_con_la_receta(monkeypatch, tmp_path):
    def reventar(corutina, *args, **extra):
        corutina.close()  # se cierra para no dejar una corrutina sin esperar
        raise RuntimeError("403, message='Invalid response status'")

    monkeypatch.setattr(modulo_edge.asyncio, "run", reventar)
    with pytest.raises(ErrorDeSintesis, match="pip install -U"):
        EdgeTTS(Config()).sintetizar("Hola", tmp_path / "a.mp3")


@pytest.mark.parametrize("version,esperado", [("7.3.1", (7, 3, 1)), ("8.0", (8, 0))])
def test_lectura_de_la_version(version, esperado):
    assert modulo_edge._como_tupla(version) == esperado
