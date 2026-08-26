"""Proveedor por defecto: las voces neuronales de Microsoft Edge (`edge-tts`).

Es la opción recomendada para empezar: no necesita clave de API, no tiene
coste y las voces en español (México, España, Colombia, Argentina…) suenan
muy naturales. Necesita conexión a internet.
"""

from __future__ import annotations

import asyncio
import os
import re
import ssl
from pathlib import Path

from voceo.errores import ErrorDeSintesis, ProveedorNoDisponible
from voceo.proveedores.base import Proveedor, Voz

#: Formatos aceptados por edge-tts para velocidad, tono y volumen.
_RE_PORCENTAJE = re.compile(r"^[+-]\d{1,3}%$")
_RE_HERCIOS = re.compile(r"^[+-]\d{1,3}Hz$")


def _importar_edge_tts():
    try:
        import edge_tts  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ProveedorNoDisponible(
            "Falta la dependencia «edge-tts». Instálala con:\n"
            "    pip install edge-tts"
        ) from exc
    return edge_tts


def _proxy() -> str | None:
    """Proxy HTTP a usar, tomado del entorno (útil en redes corporativas)."""
    for variable in ("VOCEO_PROXY", "HTTPS_PROXY", "https_proxy"):
        valor = os.environ.get(variable, "").strip()
        if valor:
            return valor
    return None


def _aplicar_certificados(edge_tts) -> None:
    """Permite usar un certificado raíz propio (proxy con inspección TLS).

    `edge-tts` fija internamente el paquete de certificados de `certifi`, así
    que si la red del centro comercial intercepta el tráfico HTTPS hay que
    indicarle explícitamente el certificado de la empresa.
    """
    ruta = os.environ.get("VOCEO_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if not ruta or not Path(ruta).is_file():
        return
    contexto = ssl.create_default_context(cafile=ruta)
    edge_tts.communicate._SSL_CTX = contexto  # noqa: SLF001
    edge_tts.voices._SSL_CTX = contexto  # noqa: SLF001


class EdgeTTS(Proveedor):
    nombre = "edge"
    formato = "mp3"
    sin_conexion = False

    def verificar(self) -> None:
        edge_tts = _importar_edge_tts()
        _aplicar_certificados(edge_tts)
        for valor, patron, campo in (
            (self.config.velocidad, _RE_PORCENTAJE, "velocidad"),
            (self.config.volumen, _RE_PORCENTAJE, "volumen"),
            (self.config.tono, _RE_HERCIOS, "tono"),
        ):
            if not patron.match(valor):
                ejemplo = "-10%" if patron is _RE_PORCENTAJE else "+5Hz"
                raise ProveedorNoDisponible(
                    f"El valor de «{campo}» debe tener la forma «{ejemplo}»; "
                    f"se recibió «{valor}»."
                )

    def sintetizar(self, texto: str, destino: Path) -> Path:
        edge_tts = _importar_edge_tts()
        _aplicar_certificados(edge_tts)
        destino = self._destino_con_formato(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)

        async def _generar() -> None:
            comunicacion = edge_tts.Communicate(
                texto,
                self.config.voz,
                rate=self.config.velocidad,
                volume=self.config.volumen,
                pitch=self.config.tono,
                proxy=_proxy(),
            )
            await comunicacion.save(str(destino))

        try:
            asyncio.run(_generar())
        except Exception as exc:  # edge-tts lanza excepciones muy variadas
            destino.unlink(missing_ok=True)
            raise ErrorDeSintesis(
                f"edge-tts no pudo generar el audio con la voz "
                f"«{self.config.voz}»: {exc}"
            ) from exc

        if not destino.exists() or destino.stat().st_size == 0:
            destino.unlink(missing_ok=True)
            raise ErrorDeSintesis(
                "edge-tts devolvió un audio vacío. Comprueba la conexión a "
                "internet y que la voz exista (voceo voces)."
            )
        return destino

    def voces(self, idioma: str | None = "es") -> list[Voz]:
        edge_tts = _importar_edge_tts()
        _aplicar_certificados(edge_tts)
        try:
            catalogo = asyncio.run(edge_tts.list_voices(proxy=_proxy()))
        except Exception as exc:
            raise ErrorDeSintesis(
                f"No se pudo consultar el catálogo de voces: {exc}"
            ) from exc

        encontradas: list[Voz] = []
        for entrada in catalogo:
            codigo = entrada.get("Locale", "")
            if idioma and not codigo.lower().startswith(idioma.lower()):
                continue
            etiquetas = entrada.get("VoiceTag", {}) or {}
            estilos = ", ".join(etiquetas.get("VoicePersonalities", []) or [])
            encontradas.append(
                Voz(
                    id=entrada.get("ShortName", ""),
                    nombre=entrada.get("FriendlyName", ""),
                    idioma=codigo,
                    genero=entrada.get("Gender", ""),
                    descripcion=estilos,
                )
            )
        return sorted(encontradas, key=lambda v: v.id)
