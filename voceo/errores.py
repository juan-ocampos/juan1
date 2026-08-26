"""Excepciones propias del proyecto.

Todas heredan de :class:`VoceoError` para que la CLI pueda distinguir un fallo
esperado (que se muestra como un mensaje claro) de un error de programación.
"""

from __future__ import annotations


class VoceoError(Exception):
    """Error esperado: se muestra al usuario sin traza de Python."""


class ErrorDeConfiguracion(VoceoError):
    """La configuración es inválida o falta un dato obligatorio."""


class ProveedorNoDisponible(VoceoError):
    """El proveedor de voz no está instalado o no está configurado."""


class ErrorDeSintesis(VoceoError):
    """El proveedor falló al convertir el texto en audio."""


class ErrorDeAudio(VoceoError):
    """Falló el procesamiento del audio (normalmente ffmpeg)."""


class ErrorDePlantilla(VoceoError):
    """La plantilla no existe o le faltan campos."""
