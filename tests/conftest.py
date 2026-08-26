"""Utilidades compartidas por las pruebas."""

from __future__ import annotations

from pathlib import Path

import pytest

from voceo import audio, proveedores
from voceo.config import Config
from voceo.proveedores.base import Proveedor, Voz


class ProveedorFalso(Proveedor):
    """Proveedor de mentira: escribe un WAV sintético en vez de llamar a un servicio."""

    nombre = "falso"
    formato = "wav"
    sin_conexion = True
    #: Textos que se le han pedido, para comprobarlos en las pruebas.
    recibidos: list[str] = []

    def verificar(self) -> None:
        return None

    def sintetizar(self, texto: str, destino: Path) -> Path:
        type(self).recibidos.append(texto)
        destino = self._destino_con_formato(destino)
        # La duración depende del texto: así se nota si se troceó.
        return audio.generar_campanilla(
            destino, notas=((440.0, max(0.2, min(len(texto) / 100, 2.0))),)
        )

    def voces(self, idioma: str | None = "es") -> list[Voz]:
        return [Voz("falsa-1", "Falsa", "es-MX", "Female", "de prueba")]


class ProveedorFalsoMp3(ProveedorFalso):
    """Como el anterior, pero declara que entrega MP3 (sin pasar por ffmpeg)."""

    nombre = "falso-mp3"
    formato = "mp3"

    def sintetizar(self, texto: str, destino: Path) -> Path:
        type(self).recibidos.append(texto)
        destino = self._destino_con_formato(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"ID3" + texto.encode("utf-8"))
        return destino


@pytest.fixture
def proveedor_falso(monkeypatch):
    """Registra los proveedores de prueba y devuelve la clase que apunta los textos."""
    ProveedorFalso.recibidos = []
    registro = dict(proveedores._REGISTRO)
    registro["falso"] = lambda: ProveedorFalso
    registro["falso-mp3"] = lambda: ProveedorFalsoMp3
    monkeypatch.setattr(proveedores, "_REGISTRO", registro)
    return ProveedorFalso


@pytest.fixture
def config_basica(tmp_path) -> Config:
    """Configuración sin adornos: no necesita ffmpeg."""
    return Config(
        proveedor="falso-mp3",
        salida=tmp_path / "audio",
        campanilla=False,
        normalizar_volumen=False,
        silencio_inicial=0.0,
        silencio_final=0.0,
        repetir=1,
    )


hace_falta_ffmpeg = pytest.mark.skipif(
    audio.ruta_ffmpeg() is None, reason="ffmpeg no está instalado"
)


@pytest.fixture
def espia_config(monkeypatch):
    """Intercepta `generador.generar` y guarda la configuración con la que se llamó."""
    from pathlib import Path as _Path

    import voceo.cli as cli
    from voceo.generador import Resultado

    capturado: dict = {}

    def espia(texto, destino, config, **extra):
        capturado["texto"] = texto
        capturado["config"] = config
        destino = _Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"ID3")
        return Resultado(
            ruta=destino,
            texto=texto,
            texto_original=texto,
            proveedor=config.proveedor,
            voz=config.voz,
        )

    monkeypatch.setattr(cli.generador, "generar", espia)
    return capturado
