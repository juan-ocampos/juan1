"""Rutas de los archivos que acompañan al paquete."""

from __future__ import annotations

from pathlib import Path

#: Carpeta del paquete instalado.
PAQUETE = Path(__file__).resolve().parent

#: Datos incluidos con el programa (plantillas de ejemplo).
DATOS = PAQUETE / "datos"

#: Plantillas de avisos que trae el programa de fábrica.
PLANTILLAS_POR_DEFECTO = DATOS / "anuncios.toml"
