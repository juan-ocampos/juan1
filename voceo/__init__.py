"""Voceo: generación de audio MP3 con voz natural para el voceo de un centro comercial."""

__version__ = "0.1.0"

from voceo.errores import (
    ErrorDeConfiguracion,
    ErrorDeSintesis,
    ProveedorNoDisponible,
    VoceoError,
)

__all__ = [
    "__version__",
    "VoceoError",
    "ErrorDeConfiguracion",
    "ErrorDeSintesis",
    "ProveedorNoDisponible",
]
