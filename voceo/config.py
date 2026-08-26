"""Configuración del programa: valores por defecto, archivo TOML y perfiles."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from voceo.errores import ErrorDeConfiguracion
from voceo.rutas import PLANTILLAS_POR_DEFECTO

# Nombre del archivo de configuración que se busca en el directorio actual.
ARCHIVO_CONFIG = "voceo.toml"

# Ubicaciones donde se busca la configuración, en orden de prioridad.
def rutas_de_busqueda() -> list[Path]:
    return [
        Path.cwd() / ARCHIVO_CONFIG,
        Path.home() / ".config" / "voceo" / ARCHIVO_CONFIG,
    ]


def normalizar_porcentaje(valor: str) -> str:
    """Admite «-10», «-10%», «10» y devuelve siempre la forma «-10%»."""
    texto = str(valor).strip().replace(" ", "")
    if not texto:
        return "+0%"
    coincidencia = re.fullmatch(r"([+-]?)(\d{1,3})%?", texto)
    if not coincidencia:
        return texto  # que el proveedor explique el error
    signo = coincidencia.group(1) or "+"
    return f"{signo}{coincidencia.group(2)}%"


def normalizar_hercios(valor: str) -> str:
    """Admite «+5», «+5Hz», «5hz» y devuelve siempre la forma «+5Hz»."""
    texto = str(valor).strip().replace(" ", "")
    if not texto:
        return "+0Hz"
    coincidencia = re.fullmatch(r"([+-]?)(\d{1,3})(?:hz)?", texto, re.IGNORECASE)
    if not coincidencia:
        return texto
    signo = coincidencia.group(1) or "+"
    return f"{signo}{coincidencia.group(2)}Hz"


@dataclass(frozen=True)
class Config:
    """Todos los ajustes que gobiernan una generación de audio."""

    # --- Motor de voz ---
    proveedor: str = "edge"
    voz: str = "es-MX-DaliaNeural"
    velocidad: str = "-5%"   # un poco más lento: se entiende mejor por megafonía
    tono: str = "+0Hz"
    volumen: str = "+0%"
    modelo: str = ""         # solo para openai / elevenlabs / piper
    instrucciones: str = ""  # estilo de lectura (solo openai)
    max_caracteres: int = 1800

    # --- Salida ---
    salida: Path = Path("audio")
    bitrate: str = "160k"
    frecuencia: int = 44100
    canales: int = 1         # mono: es lo habitual en megafonía

    # --- Producción del aviso ---
    campanilla: bool = True
    campanilla_archivo: Path | None = None
    silencio_inicial: float = 0.4
    silencio_final: float = 1.0
    repetir: int = 1
    pausa_repeticion: float = 1.5
    normalizar_volumen: bool = True

    # --- Texto ---
    expandir_abreviaturas: bool = True
    marcadores: bool = True

    # --- Plantillas ---
    #: Archivo TOML de plantillas; por defecto, el que trae el programa.
    plantillas: Path = PLANTILLAS_POR_DEFECTO

    def __post_init__(self) -> None:
        # Se aceptan formas cómodas («-10», «10%») y se guardan normalizadas.
        object.__setattr__(self, "velocidad", normalizar_porcentaje(self.velocidad))
        object.__setattr__(self, "volumen", normalizar_porcentaje(self.volumen))
        object.__setattr__(self, "tono", normalizar_hercios(self.tono))

    def con(self, **cambios: Any) -> "Config":
        """Devuelve una copia con los cambios indicados (ignora los `None`)."""
        utiles = {k: v for k, v in cambios.items() if v is not None}
        desconocidos = set(utiles) - {f.name for f in fields(self)}
        if desconocidos:
            raise ErrorDeConfiguracion(
                f"Ajustes desconocidos: {', '.join(sorted(desconocidos))}"
            )
        return replace(self, **utiles)


#: Palabras que se aceptan como «sí» y «no» en la configuración y en los CSV.
_VERDADEROS = {"1", "si", "sí", "true", "verdadero", "on", "x"}
_FALSOS = {"0", "no", "false", "falso", "off", ""}


def a_bool(valor: Any) -> bool:
    """Interpreta «sí», «no», «1», «true»… además de los booleanos de TOML."""
    if isinstance(valor, bool):
        return valor
    texto = str(valor).strip().lower()
    if texto in _VERDADEROS:
        return True
    if texto in _FALSOS:
        return False
    raise ValueError(f"no se entiende «{valor}» como sí/no")


_CONVERSORES = {
    Path: lambda v: Path(str(v)),
    int: int,
    float: float,
    bool: a_bool,
    str: str,
}


def _convertir(nombre: str, valor: Any, tipo: Any) -> Any:
    """Adapta un valor leído del TOML al tipo declarado en `Config`."""
    if nombre == "campanilla_archivo":
        return Path(str(valor)) if valor else None
    origen = tipo if tipo in _CONVERSORES else str
    try:
        return _CONVERSORES[origen](valor)
    except (TypeError, ValueError) as exc:
        raise ErrorDeConfiguracion(f"Valor inválido para «{nombre}»: {valor!r}") from exc


def aplicar(config: Config, datos: dict[str, Any], origen: str) -> Config:
    """Aplica un diccionario de ajustes (TOML, perfil o plantilla) sobre `config`."""
    tipos = {f.name: f.type for f in fields(Config)}
    cambios: dict[str, Any] = {}
    for clave, valor in datos.items():
        if clave == "perfiles":
            continue
        if clave not in tipos:
            raise ErrorDeConfiguracion(
                f"«{clave}» no es un ajuste válido (en {origen})."
            )
        tipo = tipos[clave]
        if tipo == "Path" or tipo is Path:
            cambios[clave] = _convertir(clave, valor, Path)
        elif tipo == "Path | None":
            cambios[clave] = _convertir(clave, valor, Path)
        elif tipo == "int" or tipo is int:
            cambios[clave] = _convertir(clave, valor, int)
        elif tipo == "float" or tipo is float:
            cambios[clave] = _convertir(clave, valor, float)
        elif tipo == "bool" or tipo is bool:
            cambios[clave] = _convertir(clave, valor, bool)
        else:
            cambios[clave] = _convertir(clave, valor, str)
    return config.con(**cambios)


def cargar(ruta: Path | None = None, perfil: str | None = None) -> Config:
    """Carga la configuración desde un TOML y aplica el perfil indicado.

    Si `ruta` es `None` se buscan las ubicaciones habituales; si no hay
    ninguna, se devuelven los valores por defecto.
    """
    config = Config()
    archivo: Path | None = ruta
    if archivo is None:
        archivo = next((r for r in rutas_de_busqueda() if r.is_file()), None)
    elif not archivo.is_file():
        raise ErrorDeConfiguracion(f"No existe el archivo de configuración: {archivo}")

    datos: dict[str, Any] = {}
    if archivo is not None:
        try:
            datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ErrorDeConfiguracion(f"{archivo} no es un TOML válido: {exc}") from exc
        config = aplicar(config, datos, str(archivo))

    if perfil:
        perfiles = datos.get("perfiles", {})
        if perfil not in perfiles:
            disponibles = ", ".join(sorted(perfiles)) or "ninguno"
            raise ErrorDeConfiguracion(
                f"El perfil «{perfil}» no está definido (perfiles disponibles: {disponibles})."
            )
        config = aplicar(config, perfiles[perfil], f"perfil {perfil}")

    return config


def perfiles_disponibles(ruta: Path | None = None) -> list[str]:
    """Lista los nombres de perfil definidos en el archivo de configuración."""
    archivo = ruta or next((r for r in rutas_de_busqueda() if r.is_file()), None)
    if archivo is None or not archivo.is_file():
        return []
    try:
        datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return []
    return sorted(datos.get("perfiles", {}))


def clave_api(variable: str, proveedor: str) -> str:
    """Lee una clave de API del entorno o explica cómo configurarla."""
    valor = os.environ.get(variable, "").strip()
    if not valor:
        raise ErrorDeConfiguracion(
            f"Falta la variable de entorno {variable}, necesaria para el "
            f"proveedor «{proveedor}».\n"
            f"Configúrala con:  export {variable}=\"tu-clave\""
        )
    return valor
