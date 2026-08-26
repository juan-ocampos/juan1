"""Lectura de TOML que funciona igual en Python 3.10 y en 3.11 o superior.

`tomllib` entró en la biblioteca estándar con Python 3.11. En la 3.10 se usa
`tomli`, que es exactamente la misma implementación publicada aparte, así que
el comportamiento no cambia.
"""

from __future__ import annotations

from typing import Any

try:  # Python 3.11 o superior
    import tomllib as _motor
except ModuleNotFoundError:  # Python 3.10
    try:
        import tomli as _motor  # type: ignore[no-redef]
    except ModuleNotFoundError as exc:  # pragma: no cover - depende del entorno
        raise ImportError(
            "En Python 3.10 hace falta el paquete «tomli» para leer los "
            "archivos de configuración y de plantillas.\n"
            "    pip install tomli"
        ) from exc

#: Excepción que se lanza cuando el TOML está mal escrito.
ErrorTOML = _motor.TOMLDecodeError


def leer(contenido: str) -> dict[str, Any]:
    """Interpreta un texto en formato TOML y devuelve un diccionario."""
    return _motor.loads(contenido)
