"""Pruebas de la lectura de TOML (compatible con Python 3.10 y 3.11+)."""

import builtins
import importlib
import sys

import pytest

from voceo import lector_toml


def test_lee_un_toml_normal():
    assert lector_toml.leer('voz = "es-MX-DaliaNeural"\nrepetir = 2\n') == {
        "voz": "es-MX-DaliaNeural",
        "repetir": 2,
    }


def test_un_toml_roto_lanza_error_toml():
    with pytest.raises(lector_toml.ErrorTOML):
        lector_toml.leer("esto no es toml =")


def test_usa_tomli_cuando_no_hay_tomllib(monkeypatch):
    """En Python 3.10 no existe `tomllib`: debe recurrir a `tomli`."""
    pytest.importorskip("tomli")
    importar = builtins.__import__

    def sin_tomllib(nombre, *args, **extra):
        if nombre == "tomllib":
            raise ModuleNotFoundError("No module named 'tomllib'")
        return importar(nombre, *args, **extra)

    monkeypatch.setattr(builtins, "__import__", sin_tomllib)
    monkeypatch.delitem(sys.modules, "voceo.lector_toml", raising=False)
    recargado = importlib.import_module("voceo.lector_toml")
    try:
        assert recargado._motor.__name__ == "tomli"
        assert recargado.leer("a = 1") == {"a": 1}
        with pytest.raises(recargado.ErrorTOML):
            recargado.leer("a =")
    finally:
        monkeypatch.undo()
        importlib.reload(lector_toml)
