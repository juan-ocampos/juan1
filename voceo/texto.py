"""Preparación del texto antes de enviarlo al motor de voz.

El objetivo es que un texto escrito por el personal del centro comercial
("Sr. Pérez, acuda al mód. de informes, placas ABC-123") se lea de forma
natural y sin ambigüedades por megafonía.
"""

from __future__ import annotations

import re
import unicodedata

# --- Abreviaturas frecuentes en avisos de centro comercial ---------------
# El orden importa: las claves más largas se sustituyen primero.
ABREVIATURAS: dict[str, str] = {
    "Sr.": "señor",
    "Sra.": "señora",
    "Srta.": "señorita",
    "Dr.": "doctor",
    "Dra.": "doctora",
    "Lic.": "licenciado",
    "Ing.": "ingeniero",
    "Av.": "avenida",
    "Avda.": "avenida",
    "Blvd.": "bulevar",
    "Col.": "colonia",
    "No.": "número",
    "Nº": "número",
    "N°": "número",
    "núm.": "número",
    "mód.": "módulo",
    "aprox.": "aproximadamente",
    "hrs.": "horas",
    "hs.": "horas",
    "min.": "minutos",
    "seg.": "segundos",
    "aprox": "aproximadamente",
    "PB": "planta baja",
    "P.B.": "planta baja",
    "N1": "nivel uno",
    "N2": "nivel dos",
    "N3": "nivel tres",
    "S1": "sótano uno",
    "S2": "sótano dos",
    "etc.": "etcétera",
    "dto.": "descuento",
    "dcto.": "descuento",
    "Cía.": "compañía",
    "Depto.": "departamento",
    "Edo.": "estado",
}

# Símbolos que conviene leer con palabras.
SIMBOLOS: dict[str, str] = {
    "%": " por ciento",
    "&": " y ",
    "@": " arroba ",
    "+": " más ",
    "=": " igual a ",
}

# Nombre en español de cada letra, para deletrear placas, códigos o apellidos.
LETRAS: dict[str, str] = {
    "A": "a", "B": "be", "C": "ce", "D": "de", "E": "e", "F": "efe",
    "G": "ge", "H": "hache", "I": "i", "J": "jota", "K": "ka", "L": "ele",
    "M": "eme", "N": "ene", "Ñ": "eñe", "O": "o", "P": "pe", "Q": "cu",
    "R": "erre", "S": "ese", "T": "te", "U": "u", "V": "uve", "W": "doble uve",
    "X": "equis", "Y": "i griega", "Z": "zeta",
}

DIGITOS: dict[str, str] = {
    "0": "cero", "1": "uno", "2": "dos", "3": "tres", "4": "cuatro",
    "5": "cinco", "6": "seis", "7": "siete", "8": "ocho", "9": "nueve",
}

SIGNOS_DELETREO: dict[str, str] = {
    "-": "guion",
    "_": "guion bajo",
    "/": "barra",
    ".": "punto",
    " ": "",
}

# Marcador de pausa que el usuario puede escribir en el texto.
_RE_PAUSA = re.compile(r"\[pausa(?::(\d+))?\]", re.IGNORECASE)
# Marcador para deletrear un fragmento: [deletrear:ABC-123]
_RE_DELETREAR = re.compile(r"\[deletrear:([^\]]+)\]", re.IGNORECASE)
_RE_ESPACIOS = re.compile(r"[ \t ]+")
_RE_SALTOS = re.compile(r"\n{2,}")
# Corta en el punto/interrogación/exclamación seguido de espacio.
_RE_FIN_ORACION = re.compile(r"(?<=[.!?…])\s+")


def limpiar(texto: str) -> str:
    """Quita espacios sobrantes y normaliza los saltos de línea."""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = _RE_ESPACIOS.sub(" ", texto)
    texto = _RE_SALTOS.sub("\n", texto)
    lineas = [linea.strip() for linea in texto.split("\n")]
    return "\n".join(linea for linea in lineas if linea).strip()


def deletrear(cadena: str) -> str:
    """Convierte «ABC-123» en «a, be, ce, guion, uno, dos, tres».

    Se usa para placas de vehículos, códigos de casillero o apellidos poco
    comunes, donde una lectura corrida se entiende mal por megafonía.
    """
    partes: list[str] = []
    for caracter in cadena.strip():
        mayuscula = caracter.upper()
        if mayuscula in LETRAS:
            partes.append(LETRAS[mayuscula])
        elif caracter in DIGITOS:
            partes.append(DIGITOS[caracter])
        elif caracter in SIGNOS_DELETREO:
            nombre = SIGNOS_DELETREO[caracter]
            if nombre:
                partes.append(nombre)
        else:
            # Letras acentuadas u otros signos: se leen tal cual.
            base = unicodedata.normalize("NFD", mayuscula)[0]
            partes.append(LETRAS.get(base, caracter))
    return ", ".join(partes)


def expandir_abreviaturas(texto: str) -> str:
    """Sustituye abreviaturas y símbolos por su lectura completa."""
    for abreviatura in sorted(ABREVIATURAS, key=len, reverse=True):
        patron = re.compile(
            r"(?<![\wÁÉÍÓÚÜÑáéíóúüñ])" + re.escape(abreviatura) + r"(?![\wÁÉÍÓÚÜÑáéíóúüñ])"
        )
        texto = patron.sub(ABREVIATURAS[abreviatura], texto)
    for simbolo, lectura in SIMBOLOS.items():
        texto = texto.replace(simbolo, lectura)
    return _RE_ESPACIOS.sub(" ", texto)


def aplicar_marcadores(texto: str) -> str:
    """Traduce los marcadores `[pausa]` y `[deletrear:...]` a texto hablado.

    `[pausa]` se convierte en puntos suspensivos, que todos los motores
    neuronales interpretan como un silencio breve; `[pausa:3]` alarga la
    pausa repitiéndolos.
    """
    texto = _RE_DELETREAR.sub(lambda m: deletrear(m.group(1)), texto)

    def _pausa(coincidencia: re.Match[str]) -> str:
        veces = int(coincidencia.group(1) or 1)
        veces = max(1, min(veces, 5))
        return " " + " ".join(["..."] * veces) + " "

    return _RE_PAUSA.sub(_pausa, texto)


def normalizar(
    texto: str,
    *,
    expandir: bool = True,
    marcadores: bool = True,
) -> str:
    """Deja el texto listo para el motor de voz.

    Args:
        texto: el aviso tal y como lo escribió el usuario.
        expandir: sustituir abreviaturas y símbolos por palabras.
        marcadores: interpretar `[pausa]` y `[deletrear:...]`.
    """
    resultado = limpiar(texto)
    if marcadores:
        resultado = aplicar_marcadores(resultado)
    if expandir:
        resultado = expandir_abreviaturas(resultado)
    return limpiar(resultado)


def dividir(texto: str, max_caracteres: int = 1800) -> list[str]:
    """Parte un texto largo en fragmentos que respetan el fin de oración.

    Los proveedores de voz limitan el tamaño de cada petición; los fragmentos
    se sintetizan por separado y luego se unen en un único MP3.
    """
    if max_caracteres <= 0:
        raise ValueError("max_caracteres debe ser mayor que cero")
    texto = limpiar(texto)
    if len(texto) <= max_caracteres:
        return [texto] if texto else []

    fragmentos: list[str] = []
    actual = ""
    for oracion in _RE_FIN_ORACION.split(texto):
        if not oracion:
            continue
        if len(oracion) > max_caracteres:
            # Oración kilométrica: se corta por palabras como último recurso.
            if actual:
                fragmentos.append(actual.strip())
                actual = ""
            for palabra in oracion.split(" "):
                if len(actual) + len(palabra) + 1 > max_caracteres:
                    fragmentos.append(actual.strip())
                    actual = palabra
                else:
                    actual = f"{actual} {palabra}".strip()
            continue
        if len(actual) + len(oracion) + 1 > max_caracteres:
            fragmentos.append(actual.strip())
            actual = oracion
        else:
            actual = f"{actual} {oracion}".strip()
    if actual.strip():
        fragmentos.append(actual.strip())
    return fragmentos


def nombre_de_archivo(texto: str, maximo: int = 50) -> str:
    """Propone un nombre de archivo a partir del texto del aviso."""
    sin_acentos = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", sin_acentos).strip("-").lower()
    if not limpio:
        return "aviso"
    return limpio[:maximo].rstrip("-")
