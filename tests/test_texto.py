"""Pruebas de la preparación del texto."""

import pytest

from voceo import texto


def test_expande_abreviaturas_frecuentes():
    resultado = texto.normalizar("El Sr. Pérez está en el mód. 3, Av. Reforma.")
    assert "señor Pérez" in resultado
    assert "módulo 3" in resultado
    assert "avenida Reforma" in resultado


def test_no_expande_dentro_de_una_palabra():
    # "Nova." no debe convertirse por contener "No."
    assert texto.normalizar("Tienda Nova.") == "Tienda Nova."


def test_simbolos_se_leen_con_palabras():
    assert "20 por ciento" in texto.normalizar("20% de descuento")


def test_deletrear_placas():
    assert texto.deletrear("AB-1") == "a, be, guion, uno"


def test_deletrear_ignora_acentos():
    assert texto.deletrear("Ñ") == "eñe"


def test_marcador_de_deletreo():
    resultado = texto.normalizar("Placas [deletrear:A1]")
    assert resultado == "Placas a, uno"


def test_marcador_de_pausa():
    assert "..." in texto.normalizar("Atención [pausa] gracias")
    assert texto.normalizar("Atención [pausa:2] gracias").count("...") == 2


def test_limpia_espacios_y_saltos():
    assert texto.limpiar("  hola   mundo \n\n\n  adiós  ") == "hola mundo\nadiós"


def test_dividir_respeta_el_limite():
    largo = "Frase de prueba. " * 40
    trozos = texto.dividir(largo, 100)
    assert trozos
    assert all(len(t) <= 100 for t in trozos)
    assert "".join(trozos).replace(" ", "") == largo.replace(" ", "")


def test_dividir_texto_corto_no_trocea():
    assert texto.dividir("Hola.", 100) == ["Hola."]


def test_dividir_corta_una_oracion_kilometrica():
    palabra = "palabra " * 50
    trozos = texto.dividir(palabra, 40)
    assert all(len(t) <= 40 for t in trozos)


def test_dividir_exige_un_limite_positivo():
    with pytest.raises(ValueError):
        texto.dividir("hola", 0)


def test_nombre_de_archivo_sin_acentos_ni_signos():
    assert texto.nombre_de_archivo("Cierre — 21:00 hrs.") == "cierre-21-00-hrs"


def test_nombre_de_archivo_de_texto_vacio():
    assert texto.nombre_de_archivo("¿?") == "aviso"
