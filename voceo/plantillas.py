"""Plantillas de avisos: los textos que se repiten a diario en el centro comercial.

Se definen en un archivo TOML (por defecto `plantillas/anuncios.toml`) para que
el personal pueda añadir o corregir avisos sin tocar el código.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from voceo.errores import ErrorDePlantilla
from voceo.lector_toml import ErrorTOML, leer as leer_toml
from voceo.rutas import PLANTILLAS_POR_DEFECTO
from voceo.texto import deletrear

#: Ruta que se usa si la configuración no indica otra.
RUTA_POR_DEFECTO = PLANTILLAS_POR_DEFECTO


@dataclass(frozen=True)
class Plantilla:
    """Un aviso reutilizable con huecos que se rellenan al vocearlo."""

    nombre: str
    texto: str
    descripcion: str = ""
    campos: tuple[str, ...] = ()
    deletrear: tuple[str, ...] = ()
    por_defecto: dict[str, str] = field(default_factory=dict)
    ajustes: dict[str, Any] = field(default_factory=dict)

    @property
    def obligatorios(self) -> tuple[str, ...]:
        """Campos que hay que dar sí o sí (no tienen valor por defecto)."""
        return tuple(c for c in self.campos if c not in self.por_defecto)

    def rellenar(self, valores: dict[str, str]) -> str:
        """Sustituye los huecos por los valores dados.

        Los campos marcados en `deletrear` se convierten a lectura letra a
        letra, para que una placa o un código se entiendan por megafonía.
        """
        desconocidos = sorted(set(valores) - set(self.campos))
        if desconocidos:
            raise ErrorDePlantilla(
                f"La plantilla «{self.nombre}» no tiene los campos: "
                f"{', '.join(desconocidos)}. Campos válidos: "
                f"{', '.join(self.campos) or 'ninguno'}."
            )

        completos = dict(self.por_defecto)
        completos.update({k: v for k, v in valores.items() if v is not None})

        faltantes = sorted(set(self.campos) - set(completos))
        if faltantes:
            ejemplo = " ".join(f"--campo {c}=..." for c in faltantes)
            raise ErrorDePlantilla(
                f"Faltan campos de la plantilla «{self.nombre}»: "
                f"{', '.join(faltantes)}.\n  Añádelos así:  {ejemplo}"
            )

        for campo in self.deletrear:
            if campo in completos:
                completos[campo] = deletrear(str(completos[campo]))

        try:
            return string.Formatter().vformat(self.texto, (), completos)
        except (KeyError, IndexError) as exc:
            raise ErrorDePlantilla(
                f"La plantilla «{self.nombre}» usa un hueco no declarado en "
                f"«campos»: {exc}"
            ) from exc


def _huecos(texto: str) -> set[str]:
    """Nombres de los `{huecos}` que aparecen en el texto."""
    return {
        nombre
        for _, nombre, _, _ in string.Formatter().parse(texto)
        if nombre
    }


def cargar(ruta: Path | None = None) -> dict[str, Plantilla]:
    """Lee todas las plantillas del archivo TOML indicado."""
    archivo = Path(ruta) if ruta else RUTA_POR_DEFECTO
    if not archivo.is_file():
        raise ErrorDePlantilla(f"No se encontró el archivo de plantillas: {archivo}")
    try:
        datos = leer_toml(archivo.read_text(encoding="utf-8"))
    except ErrorTOML as exc:
        raise ErrorDePlantilla(f"{archivo} no es un TOML válido: {exc}") from exc

    plantillas: dict[str, Plantilla] = {}
    for nombre, definicion in datos.items():
        if not isinstance(definicion, dict) or "texto" not in definicion:
            raise ErrorDePlantilla(
                f"La plantilla «{nombre}» de {archivo} no define «texto»."
            )
        texto = re.sub(r"\s+", " ", str(definicion["texto"])).strip()
        campos = tuple(definicion.get("campos", sorted(_huecos(texto))))
        sin_declarar = sorted(_huecos(texto) - set(campos))
        if sin_declarar:
            raise ErrorDePlantilla(
                f"La plantilla «{nombre}» usa huecos no declarados en «campos»: "
                f"{', '.join(sin_declarar)}."
            )
        plantillas[nombre] = Plantilla(
            nombre=nombre,
            texto=texto,
            descripcion=str(definicion.get("descripcion", "")),
            campos=campos,
            deletrear=tuple(definicion.get("deletrear", ())),
            por_defecto={
                k: str(v) for k, v in (definicion.get("por_defecto", {}) or {}).items()
            },
            ajustes=dict(definicion.get("ajustes", {}) or {}),
        )
    return plantillas


def obtener(nombre: str, ruta: Path | None = None) -> Plantilla:
    """Devuelve una plantilla por su nombre, con sugerencia si no existe."""
    plantillas = cargar(ruta)
    if nombre in plantillas:
        return plantillas[nombre]
    parecidas = [n for n in plantillas if nombre.lower() in n.lower()]
    pista = f" ¿Quisiste decir: {', '.join(parecidas)}?" if parecidas else ""
    raise ErrorDePlantilla(
        f"No existe la plantilla «{nombre}».{pista}\n"
        f"Ver todas con:  voceo plantillas"
    )
