"""Pruebas de la generación por lotes desde un CSV."""

import csv

import pytest

from voceo import lote
from voceo.errores import VoceoError


def _csv(tmp_path, contenido, nombre="avisos.csv"):
    ruta = tmp_path / nombre
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_lee_csv_separado_por_comas(tmp_path):
    ruta = _csv(tmp_path, "archivo,texto\na.mp3,Hola\n")
    assert lote.leer_csv(ruta) == [{"archivo": "a.mp3", "texto": "Hola"}]


def test_lee_csv_separado_por_punto_y_coma(tmp_path):
    ruta = _csv(tmp_path, "archivo;texto\na.mp3;Hola\n")
    assert lote.leer_csv(ruta) == [{"archivo": "a.mp3", "texto": "Hola"}]


def test_csv_vacio(tmp_path):
    with pytest.raises(VoceoError, match="vacío"):
        lote.leer_csv(_csv(tmp_path, "   "))


def test_csv_sin_filas(tmp_path):
    with pytest.raises(VoceoError, match="ninguna fila"):
        lote.leer_csv(_csv(tmp_path, "archivo,texto\n"))


def test_csv_inexistente(tmp_path):
    with pytest.raises(VoceoError, match="No existe"):
        lote.leer_csv(tmp_path / "no-existe.csv")


def test_texto_de_fila_desde_plantilla(config_basica):
    fila = {"plantilla": "llamado_persona", "nombre": "Ana", "lugar": "caja 3"}
    resultado = lote.texto_de_fila(fila, config_basica)
    assert "Ana" in resultado and "caja 3" in resultado


def test_texto_de_fila_a_mano_gana_a_la_plantilla(config_basica):
    fila = {"texto": "Aviso suelto", "plantilla": "llamado_persona"}
    assert lote.texto_de_fila(fila, config_basica) == "Aviso suelto"


def test_fila_sin_texto_ni_plantilla(config_basica):
    with pytest.raises(VoceoError, match="texto"):
        lote.texto_de_fila({"archivo": "a.mp3"}, config_basica)


def test_los_ajustes_de_la_fila_se_aplican(config_basica):
    config = lote.config_de_fila(config_basica, {"repetir": "3", "campanilla": "no"}, 1)
    assert config.repetir == 3
    assert config.campanilla is False


def test_las_columnas_vacias_no_pisan_la_configuracion(config_basica):
    config = lote.config_de_fila(config_basica, {"repetir": "", "voz": ""}, 1)
    assert config.repetir == config_basica.repetir
    assert config.voz == config_basica.voz


def test_procesa_todas_las_filas(proveedor_falso, config_basica, tmp_path):
    ruta = _csv(
        tmp_path,
        "archivo,plantilla,nombre\n"
        "uno.mp3,llamado_persona,Ana\n"
        "dos.mp3,llamado_persona,Luis\n",
    )
    resumen = lote.procesar(ruta, tmp_path / "salida", config_basica)
    assert len(resumen.generados) == 2
    assert not resumen.fallidos
    assert (tmp_path / "salida" / "uno.mp3").exists()
    assert (tmp_path / "salida" / "dos.mp3").exists()


def test_una_fila_mala_no_detiene_el_lote(proveedor_falso, config_basica, tmp_path):
    ruta = _csv(
        tmp_path,
        "archivo,plantilla,nombre\n"
        "buena.mp3,llamado_persona,Ana\n"
        "mala.mp3,plantilla_que_no_existe,Luis\n",
    )
    resumen = lote.procesar(ruta, tmp_path / "salida", config_basica)
    assert len(resumen.generados) == 1
    assert len(resumen.fallidos) == 1
    assert resumen.fallidos[0].numero == 2
    assert resumen.total == 2


def test_omite_los_que_ya_existen(proveedor_falso, config_basica, tmp_path):
    ruta = _csv(tmp_path, "archivo,texto\nuno.mp3,Hola\n")
    carpeta = tmp_path / "salida"
    lote.procesar(ruta, carpeta, config_basica)
    resumen = lote.procesar(ruta, carpeta, config_basica)
    assert resumen.omitidos and not resumen.generados


def test_sobrescribir_regenera(proveedor_falso, config_basica, tmp_path):
    ruta = _csv(tmp_path, "archivo,texto\nuno.mp3,Hola\n")
    carpeta = tmp_path / "salida"
    lote.procesar(ruta, carpeta, config_basica)
    resumen = lote.procesar(ruta, carpeta, config_basica, sobrescribir=True)
    assert len(resumen.generados) == 1


def test_nombre_automatico_si_no_hay_columna_archivo(proveedor_falso, config_basica, tmp_path):
    ruta = _csv(tmp_path, "texto\nCierre en quince minutos\n")
    resumen = lote.procesar(ruta, tmp_path / "salida", config_basica)
    assert resumen.generados[0].ruta.name == "01-cierre-en-quince-minutos.mp3"


def test_escribe_el_manifiesto(proveedor_falso, config_basica, tmp_path):
    ruta = _csv(tmp_path, "archivo,texto\nuno.mp3,Hola a todos\n")
    carpeta = tmp_path / "salida"
    lote.procesar(ruta, carpeta, config_basica)
    manifiesto = carpeta / "manifiesto.csv"
    assert manifiesto.exists()
    filas = list(csv.DictReader(manifiesto.read_text(encoding="utf-8").splitlines()))
    assert filas[0]["archivo"] == "uno.mp3"
    assert filas[0]["texto"] == "Hola a todos"


def test_las_filas_en_blanco_se_ignoran(proveedor_falso, config_basica, tmp_path):
    ruta = _csv(tmp_path, "archivo,texto\nuno.mp3,Hola\n,\n")
    resumen = lote.procesar(ruta, tmp_path / "salida", config_basica)
    assert resumen.total == 1
