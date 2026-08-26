"""Generación por lotes: un CSV con muchos avisos y una carpeta de MP3.

Pensado para que el personal prepare la lista de avisos del día en una hoja de
cálculo, la exporte a CSV y genere todos los audios de una vez.

Columnas reconocidas (todas opcionales salvo `texto` o `plantilla`):

    archivo     nombre del MP3 de salida (sin ruta)
    texto       el aviso, escrito a mano
    plantilla   nombre de una plantilla, en lugar de `texto`
    proveedor, voz, velocidad, tono, volumen, repetir, campanilla
                ajustes que solo afectan a esa fila

Cualquier otra columna se toma como campo de la plantilla.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from voceo import plantillas as modulo_plantillas
from voceo import texto as modulo_texto
from voceo.config import Config, aplicar
from voceo.errores import VoceoError
from voceo.generador import Resultado, generar

#: Columnas que configuran la fila en vez de rellenar la plantilla.
COLUMNAS_RESERVADAS = {
    "archivo",
    "texto",
    "plantilla",
    "proveedor",
    "voz",
    "velocidad",
    "tono",
    "volumen",
    "repetir",
    "campanilla",
    "normalizar_volumen",
    "silencio_inicial",
    "silencio_final",
    "pausa_repeticion",
}

#: Columnas reservadas que además son ajustes de `Config`.
_AJUSTES = COLUMNAS_RESERVADAS - {"archivo", "texto", "plantilla"}


@dataclass
class FilaFallida:
    numero: int
    archivo: str
    error: str


@dataclass
class ResumenLote:
    """Qué se generó y qué falló al procesar el CSV."""

    generados: list[Resultado] = field(default_factory=list)
    omitidos: list[str] = field(default_factory=list)
    fallidos: list[FilaFallida] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.generados) + len(self.omitidos) + len(self.fallidos)


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    """Lee el CSV admitiendo coma o punto y coma como separador."""
    if not ruta.is_file():
        raise VoceoError(f"No existe el archivo de lote: {ruta}")
    contenido = ruta.read_text(encoding="utf-8-sig")
    if not contenido.strip():
        raise VoceoError(f"El archivo de lote está vacío: {ruta}")
    try:
        dialecto = csv.Sniffer().sniff(contenido.splitlines()[0], delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel  # una sola columna: da igual el separador
    filas = list(csv.DictReader(contenido.splitlines(), dialect=dialecto))
    if not filas:
        raise VoceoError(f"El archivo {ruta} no tiene ninguna fila de datos.")
    return [{(k or "").strip(): (v or "").strip() for k, v in fila.items()} for fila in filas]


def config_de_fila(config: Config, fila: dict[str, str], numero: int = 0) -> Config:
    """Aplica a `config` los ajustes que traiga esa fila del CSV."""
    ajustes = {
        clave: valor
        for clave, valor in fila.items()
        if clave in _AJUSTES and valor != ""
    }
    return aplicar(config, ajustes, f"fila {numero}") if ajustes else config


def texto_de_fila(
    fila: dict[str, str], config: Config, ruta_plantillas: Path | None = None
) -> str:
    """Texto final de una fila: el escrito a mano o el de su plantilla."""
    if fila.get("texto"):
        return fila["texto"]
    nombre = fila.get("plantilla", "")
    if not nombre:
        raise VoceoError("la fila no tiene ni «texto» ni «plantilla»")
    plantilla = modulo_plantillas.obtener(nombre, ruta_plantillas or config.plantillas)
    valores = {
        clave: valor
        for clave, valor in fila.items()
        if clave and clave not in COLUMNAS_RESERVADAS and valor != ""
    }
    return plantilla.rellenar(valores)


def _nombre_de_salida(fila: dict[str, str], contenido: str, numero: int) -> str:
    if fila.get("archivo"):
        nombre = Path(fila["archivo"]).name
        return nombre if nombre.lower().endswith(".mp3") else f"{nombre}.mp3"
    base = fila.get("plantilla") or modulo_texto.nombre_de_archivo(contenido)
    return f"{numero:02d}-{modulo_texto.nombre_de_archivo(base)}.mp3"


def procesar(
    ruta_csv: Path,
    carpeta: Path,
    config: Config,
    *,
    sobrescribir: bool = False,
    ruta_plantillas: Path | None = None,
    al_empezar: Callable[[int, str], None] | None = None,
    al_terminar: Callable[[Resultado], None] | None = None,
) -> ResumenLote:
    """Genera un MP3 por cada fila del CSV dentro de `carpeta`.

    Un fallo en una fila no interrumpe el resto: se anota y se continúa.
    """
    filas = leer_csv(ruta_csv)
    carpeta.mkdir(parents=True, exist_ok=True)
    resumen = ResumenLote()

    for numero, fila in enumerate(filas, start=1):
        if not any(fila.values()):
            continue
        archivo = fila.get("archivo") or f"fila {numero}"
        try:
            config_fila = config_de_fila(config, fila, numero)
            contenido = texto_de_fila(fila, config_fila, ruta_plantillas)
            nombre = _nombre_de_salida(fila, contenido, numero)
            destino = carpeta / nombre
            if destino.exists() and not sobrescribir:
                resumen.omitidos.append(str(destino))
                continue
            if al_empezar:
                al_empezar(numero, nombre)
            resultado = generar(contenido, destino, config_fila)
            resumen.generados.append(resultado)
            if al_terminar:
                al_terminar(resultado)
        except VoceoError as exc:
            resumen.fallidos.append(FilaFallida(numero, archivo, str(exc)))
        except Exception as exc:  # un fallo raro no debe tumbar el lote entero
            resumen.fallidos.append(
                FilaFallida(numero, archivo, f"{type(exc).__name__}: {exc}")
            )

    if resumen.generados:
        escribir_manifiesto(carpeta / "manifiesto.csv", resumen.generados)
    return resumen


def escribir_manifiesto(ruta: Path, resultados: Iterable[Resultado]) -> Path:
    """Deja constancia de qué audio corresponde a qué texto."""
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(
            ["archivo", "duracion_s", "proveedor", "voz", "texto"]
        )
        for resultado in resultados:
            escritor.writerow(
                [
                    resultado.ruta.name,
                    "" if resultado.duracion is None else f"{resultado.duracion:.2f}",
                    resultado.proveedor,
                    resultado.voz,
                    resultado.texto,
                ]
            )
    return ruta
