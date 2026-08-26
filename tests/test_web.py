"""Pruebas de la aplicación web."""

import base64
import csv
import io
import zipfile

import pytest

from voceo.web import crear_app


@pytest.fixture
def cliente(proveedor_falso, config_basica):
    app = crear_app(config_basica)
    app.config["TESTING"] = True
    return app.test_client()


def _json(respuesta):
    return respuesta.get_json()


# --- páginas -------------------------------------------------------------
def test_la_pagina_carga_con_las_plantillas(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    html = respuesta.data.decode()
    assert "llamado_persona" in html
    assert "window.VOCEO" in html


def test_salud(cliente):
    assert _json(cliente.get("/salud"))["estado"] == "ok"


def test_los_estaticos_se_sirven(cliente):
    assert cliente.get("/estaticos/estilo.css").status_code == 200
    assert cliente.get("/estaticos/voceo.js").status_code == 200


def test_voces(cliente):
    voces = _json(cliente.get("/voces"))
    assert voces[0]["id"] == "falsa-1"


def test_las_voces_se_cachean(cliente, proveedor_falso, monkeypatch):
    primera = _json(cliente.get("/voces"))
    # Si volviera a consultar al proveedor, esto reventaría.
    def reventar(self, idioma=None):
        raise AssertionError("no debería volver a consultar el catálogo")

    monkeypatch.setattr(proveedor_falso, "voces", reventar)
    assert _json(cliente.get("/voces")) == primera


# --- previsualización ----------------------------------------------------
def test_previsualizar_un_texto(cliente):
    datos = _json(cliente.post("/previsualizar", json={"texto": "El Sr. López"}))
    assert datos["texto"] == "El señor López"


def test_previsualizar_una_plantilla(cliente):
    datos = _json(
        cliente.post(
            "/previsualizar",
            json={"plantilla": "llamado_persona", "campos": {"nombre": "Ana"}},
        )
    )
    assert "Ana" in datos["texto"]


def test_previsualizar_sin_texto_da_error(cliente):
    respuesta = cliente.post("/previsualizar", json={"texto": "   "})
    assert respuesta.status_code == 400
    assert "texto" in _json(respuesta)["error"].lower()


def test_falta_un_campo_obligatorio(cliente):
    respuesta = cliente.post("/previsualizar", json={"plantilla": "llamado_persona"})
    assert respuesta.status_code == 400
    assert "nombre" in _json(respuesta)["error"]


def test_plantilla_inexistente(cliente):
    respuesta = cliente.post("/previsualizar", json={"plantilla": "inventada"})
    assert respuesta.status_code == 400


def test_un_texto_larguisimo_se_rechaza(cliente):
    respuesta = cliente.post("/previsualizar", json={"texto": "a" * 6000})
    assert respuesta.status_code == 400
    assert "largo" in _json(respuesta)["error"]


# --- generación ----------------------------------------------------------
def test_generar_devuelve_un_mp3(cliente):
    respuesta = cliente.post("/generar", json={"texto": "Cierre en quince minutos"})
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "audio/mpeg"
    assert respuesta.data
    assert respuesta.headers["X-Voceo-Archivo"].endswith(".mp3")


def test_el_nombre_del_archivo_se_respeta(cliente):
    respuesta = cliente.post(
        "/generar", json={"texto": "Hola", "archivo": "Cierre 21:00"}
    )
    assert respuesta.headers["X-Voceo-Archivo"] == "cierre-21-00.mp3"


def test_generar_desde_una_plantilla(cliente):
    respuesta = cliente.post(
        "/generar",
        json={"plantilla": "llamado_persona", "campos": {"nombre": "Ana"}},
    )
    assert respuesta.status_code == 200
    assert respuesta.headers["X-Voceo-Archivo"] == "llamado-persona.mp3"


def test_los_ajustes_del_formulario_llegan(cliente, monkeypatch):
    import voceo.web.app as web

    visto = {}
    original = web.generador.generar

    def espia(texto, destino, config, **extra):
        visto["config"] = config
        return original(texto, destino, config, **extra)

    monkeypatch.setattr(web.generador, "generar", espia)
    cliente.post(
        "/generar",
        json={"texto": "Hola", "voz": "otra-voz", "velocidad": "-20%", "repetir": "2",
              "campanilla": False},
    )
    assert visto["config"].voz == "otra-voz"
    assert visto["config"].velocidad == "-20%"
    assert visto["config"].repetir == 2
    assert visto["config"].campanilla is False


def test_las_repeticiones_tienen_tope(cliente, monkeypatch):
    import voceo.web.app as web

    visto = {}
    original = web.generador.generar

    def espia(texto, destino, config, **extra):
        visto["config"] = config
        return original(texto, destino, config, **extra)

    monkeypatch.setattr(web.generador, "generar", espia)
    cliente.post("/generar", json={"texto": "Hola", "repetir": "99"})
    assert visto["config"].repetir == 3


# --- lotes ---------------------------------------------------------------
def _subir_csv(cliente, contenido, **campos):
    datos = {"csv": (io.BytesIO(contenido.encode("utf-8")), "avisos.csv"), **campos}
    return cliente.post("/lote", data=datos, content_type="multipart/form-data")


def test_lote_devuelve_un_zip(cliente):
    respuesta = _subir_csv(cliente, "archivo,texto\nuno.mp3,Hola\ndos.mp3,Adiós\n")
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "application/zip"
    assert respuesta.headers["X-Voceo-Generados"] == "2"

    with zipfile.ZipFile(io.BytesIO(respuesta.data)) as comprimido:
        nombres = comprimido.namelist()
        assert "uno.mp3" in nombres and "dos.mp3" in nombres
        assert "manifiesto.csv" in nombres
        manifiesto = comprimido.read("manifiesto.csv").decode("utf-8")
    filas = list(csv.DictReader(manifiesto.splitlines()))
    assert filas[0]["texto"] == "Hola"


def test_lote_con_filas_malas_incluye_el_informe(cliente):
    respuesta = _subir_csv(
        cliente, "archivo,texto,plantilla\nuno.mp3,Hola,\ndos.mp3,,inventada\n"
    )
    assert respuesta.status_code == 200
    assert respuesta.headers["X-Voceo-Fallidos"] == "1"
    with zipfile.ZipFile(io.BytesIO(respuesta.data)) as comprimido:
        assert "errores.csv" in comprimido.namelist()


def test_lote_sin_archivo(cliente):
    respuesta = cliente.post("/lote", data={}, content_type="multipart/form-data")
    assert respuesta.status_code == 400
    assert "CSV" in _json(respuesta)["error"]


def test_lote_con_demasiadas_filas(cliente):
    filas = "archivo,texto\n" + "".join(f"a{i}.mp3,Hola\n" for i in range(201))
    respuesta = _subir_csv(cliente, filas)
    assert respuesta.status_code == 400
    assert "máximo" in _json(respuesta)["error"]


def test_lote_donde_falla_todo(cliente):
    respuesta = _subir_csv(cliente, "archivo,plantilla\nuno.mp3,inventada\n")
    assert respuesta.status_code == 400


# --- contraseña ----------------------------------------------------------
@pytest.fixture
def cliente_protegido(proveedor_falso, config_basica, monkeypatch):
    monkeypatch.setenv("VOCEO_CLAVE", "secreta")
    app = crear_app(config_basica)
    app.config["TESTING"] = True
    return app.test_client()


def _basica(usuario, clave):
    par = base64.b64encode(f"{usuario}:{clave}".encode()).decode()
    return {"Authorization": f"Basic {par}"}


def test_sin_clave_no_se_entra(cliente_protegido):
    respuesta = cliente_protegido.get("/")
    assert respuesta.status_code == 401
    assert "Basic" in respuesta.headers["WWW-Authenticate"]


def test_con_la_clave_correcta_se_entra(cliente_protegido):
    respuesta = cliente_protegido.get("/", headers=_basica("voceo", "secreta"))
    assert respuesta.status_code == 200


def test_con_la_clave_incorrecta_no(cliente_protegido):
    respuesta = cliente_protegido.get("/", headers=_basica("voceo", "otra"))
    assert respuesta.status_code == 401


def test_la_salud_no_pide_clave(cliente_protegido):
    assert cliente_protegido.get("/salud").status_code == 200
