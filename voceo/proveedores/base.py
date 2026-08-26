"""Interfaz común a todos los motores de voz."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from voceo.config import Config


@dataclass(frozen=True)
class Voz:
    """Una voz ofrecida por un proveedor."""

    id: str
    nombre: str
    idioma: str = ""
    genero: str = ""
    descripcion: str = ""

    def __str__(self) -> str:
        partes = [self.id]
        if self.genero:
            partes.append(self.genero)
        if self.descripcion:
            partes.append(self.descripcion)
        return "  ".join(partes)


class Proveedor(ABC):
    """Motor de texto a voz.

    Cada implementación se encarga de una sola cosa: convertir un texto en un
    archivo de audio. El recorte, la campanilla, las repeticiones y la
    normalización de volumen los hace :mod:`voceo.audio`.
    """

    #: Identificador que se usa en la CLI y en la configuración.
    nombre: str = ""
    #: Extensión del audio que entrega (`mp3` o `wav`).
    formato: str = "mp3"
    #: Si funciona sin conexión a internet.
    sin_conexion: bool = False

    def __init__(self, config: Config) -> None:
        self.config = config

    @abstractmethod
    def verificar(self) -> None:
        """Comprueba dependencias y credenciales.

        Debe lanzar :class:`~voceo.errores.ProveedorNoDisponible` o
        :class:`~voceo.errores.ErrorDeConfiguracion` con un mensaje que
        explique cómo solucionarlo.
        """

    @abstractmethod
    def sintetizar(self, texto: str, destino: Path) -> Path:
        """Convierte `texto` en audio y lo guarda en `destino`.

        Devuelve la ruta escrita (puede diferir de `destino` en la extensión
        si el proveedor solo entrega WAV).
        """

    def voces(self, idioma: str | None = "es") -> list[Voz]:
        """Lista las voces disponibles, opcionalmente filtradas por idioma."""
        return []

    # --- utilidades compartidas -----------------------------------------
    def _destino_con_formato(self, destino: Path) -> Path:
        """Ajusta la extensión de `destino` al formato nativo del proveedor."""
        if destino.suffix.lower().lstrip(".") == self.formato:
            return destino
        return destino.with_suffix(f".{self.formato}")
