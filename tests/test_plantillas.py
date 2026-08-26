"""Pruebas de las plantillas de avisos."""

import pytest

from voceo import plantillas as modulo
from voceo.errores import ErrorDePlantilla


def _archivo(tmp_path, contenido):
    ruta = tmp_path / "avisos.toml"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_las_plantillas_de_fabrica_cargan():
    catalogo = modulo.cargar()
    assert "llamado_persona" in catalogo
    assert "evacuacion" in catalogo
    for plantilla in catalogo.values():
        assert plantilla.texto
        assert plantilla.descripcion


def test_todas_las_plantillas_se_pueden_rellenar():
    """Cada plantilla debe funcionar dando solo sus campos obligatorios."""
    for plantilla in modulo.cargar().values():
        valores = {campo: "prueba" for campo in plantilla.obligatorios}
        resultado = plantilla.rellenar(valores)
        assert "{" not in resultado


def test_rellenar_usa_los_valores_por_defecto(tmp_path):
    ruta = _archivo(
        tmp_path,
        '[aviso]\ntexto = "Vaya a {lugar}"\ncampos = ["lugar"]\n'
        '[aviso.por_defecto]\nlugar = "el módulo"\n',
    )
    assert modulo.obtener("aviso", ruta).rellenar({}) == "Vaya a el módulo"


def test_el_valor_dado_gana_al_por_defecto(tmp_path):
    ruta = _archivo(
        tmp_path,
        '[aviso]\ntexto = "Vaya a {lugar}"\ncampos = ["lugar"]\n'
        '[aviso.por_defecto]\nlugar = "el módulo"\n',
    )
    assert modulo.obtener("aviso", ruta).rellenar({"lugar": "caja 3"}) == "Vaya a caja 3"


def test_campo_obligatorio_ausente(tmp_path):
    ruta = _archivo(tmp_path, '[aviso]\ntexto = "Hola {nombre}"\ncampos = ["nombre"]\n')
    with pytest.raises(ErrorDePlantilla, match="nombre"):
        modulo.obtener("aviso", ruta).rellenar({})


def test_campo_desconocido(tmp_path):
    ruta = _archivo(tmp_path, '[aviso]\ntexto = "Hola"\ncampos = []\n')
    with pytest.raises(ErrorDePlantilla, match="color"):
        modulo.obtener("aviso", ruta).rellenar({"color": "rojo"})


def test_campos_marcados_se_deletrean(tmp_path):
    ruta = _archivo(
        tmp_path,
        '[aviso]\ntexto = "Placas {placas}"\ncampos = ["placas"]\ndeletrear = ["placas"]\n',
    )
    assert modulo.obtener("aviso", ruta).rellenar({"placas": "A1"}) == "Placas a, uno"


def test_hueco_no_declarado_da_error(tmp_path):
    ruta = _archivo(tmp_path, '[aviso]\ntexto = "Hola {nombre}"\ncampos = []\n')
    with pytest.raises(ErrorDePlantilla, match="nombre"):
        modulo.cargar(ruta)


def test_campos_se_deducen_si_no_se_declaran(tmp_path):
    ruta = _archivo(tmp_path, '[aviso]\ntexto = "Hola {nombre}"\n')
    assert modulo.obtener("aviso", ruta).campos == ("nombre",)


def test_plantilla_sin_texto(tmp_path):
    ruta = _archivo(tmp_path, '[aviso]\ndescripcion = "sin texto"\n')
    with pytest.raises(ErrorDePlantilla, match="texto"):
        modulo.cargar(ruta)


def test_plantilla_inexistente_sugiere_parecidas():
    with pytest.raises(ErrorDePlantilla, match="llamado_persona"):
        modulo.obtener("llamado")


def test_archivo_de_plantillas_inexistente(tmp_path):
    with pytest.raises(ErrorDePlantilla):
        modulo.cargar(tmp_path / "no-existe.toml")


def test_los_ajustes_de_la_plantilla_se_leen():
    evacuacion = modulo.obtener("evacuacion")
    assert evacuacion.ajustes["repetir"] == 2


def test_el_error_lleva_los_campos_que_faltan(tmp_path):
    ruta = _archivo(
        tmp_path, '[aviso]\ntexto = "{uno} {dos}"\ncampos = ["uno", "dos"]\n'
    )
    with pytest.raises(ErrorDePlantilla) as fallo:
        modulo.obtener("aviso", ruta).rellenar({"uno": "a"})
    assert fallo.value.faltantes == ("dos",)
    # El mensaje base no habla de la línea de órdenes: también lo lee la web.
    assert "--campo" not in str(fallo.value)
