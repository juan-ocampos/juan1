"""Registro de proveedores de voz.

Las importaciones son perezosas: instalar `edge-tts` no obliga a instalar
`openai` ni `elevenlabs`.
"""

from __future__ import annotations

from typing import Callable

from voceo.config import Config
from voceo.errores import ProveedorNoDisponible
from voceo.proveedores.base import Proveedor, Voz

#: Descripción corta de cada proveedor, para la ayuda de la CLI.
DESCRIPCIONES: dict[str, str] = {
    "edge": "Voces neuronales de Microsoft Edge. Gratis, sin clave, requiere internet.",
    "openai": "OpenAI TTS. Muy natural y con instrucciones de estilo. Requiere OPENAI_API_KEY.",
    "elevenlabs": "ElevenLabs. La opción de mayor calidad. Requiere ELEVENLABS_API_KEY.",
    "piper": "Piper: voces neuronales locales. Funciona sin internet.",
}


def _cargar_edge() -> type[Proveedor]:
    from voceo.proveedores.edge import EdgeTTS

    return EdgeTTS


def _cargar_openai() -> type[Proveedor]:
    from voceo.proveedores.openai_tts import OpenAITTS

    return OpenAITTS


def _cargar_elevenlabs() -> type[Proveedor]:
    from voceo.proveedores.elevenlabs import ElevenLabsTTS

    return ElevenLabsTTS


def _cargar_piper() -> type[Proveedor]:
    from voceo.proveedores.piper import PiperTTS

    return PiperTTS


_REGISTRO: dict[str, Callable[[], type[Proveedor]]] = {
    "edge": _cargar_edge,
    "openai": _cargar_openai,
    "elevenlabs": _cargar_elevenlabs,
    "piper": _cargar_piper,
}


def nombres() -> list[str]:
    """Nombres de los proveedores registrados."""
    return list(_REGISTRO)


def obtener(nombre: str, config: Config) -> Proveedor:
    """Instancia el proveedor `nombre` con la configuración dada."""
    clave = nombre.strip().lower()
    if clave not in _REGISTRO:
        raise ProveedorNoDisponible(
            f"«{nombre}» no es un proveedor conocido. "
            f"Opciones: {', '.join(nombres())}."
        )
    return _REGISTRO[clave]()(config)


__all__ = ["DESCRIPCIONES", "Proveedor", "Voz", "nombres", "obtener"]
