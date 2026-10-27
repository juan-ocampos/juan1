"""Proveedor por defecto: las voces neuronales de Microsoft Edge (`edge-tts`).

Es la opción recomendada para empezar: no necesita clave de API, no tiene
coste y las voces en español (México, España, Colombia, Argentina…) suenan
muy naturales. Necesita conexión a internet.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import os
import re
import ssl
from pathlib import Path

from voceo.errores import ErrorDeSintesis, ProveedorNoDisponible
from voceo.proveedores.base import Proveedor, Voz

#: Formatos aceptados por edge-tts para velocidad, tono y volumen.
_RE_PORCENTAJE = re.compile(r"^[+-]\d{1,3}%$")
_RE_HERCIOS = re.compile(r"^[+-]\d{1,3}Hz$")

#: Versión mínima que habla el esquema de testigo vigente.
#:
#: El servicio firma cada petición con un testigo («Sec-MS-GEC») cuyo esquema
#: Microsoft cambia cada cierto tiempo. Cuando lo hace, las versiones de
#: edge-tts anteriores al cambio empiezan a recibir 403. La 7.3.1 pasó del
#: esquema «1-» al «2-».
VERSION_MINIMA = "7.3.1"

_PISTA_403 = (
    "\n\nUn 403 de Microsoft casi siempre significa que la versión instalada de "
    "edge-tts se quedó atrás: el servicio firma cada petición con un testigo "
    "cuyo esquema cambia de vez en cuando, y cada versión de edge-tts trae el "
    "esquema del momento.\n"
    f'  1. Actualízala:  pip install -U "edge-tts>={VERSION_MINIMA}"\n'
    "  2. Si sigue fallando, revisa el reloj del equipo: el testigo depende de "
    "la hora y un desfase de varios minutos también da 403."
)


def _es_403(exc: BaseException) -> bool:
    """¿El fallo viene de que el servicio devolvió un 403?"""
    if getattr(exc, "status", None) == 403:
        return True
    return re.search(r"\b403\b", str(exc)) is not None


def _mensaje_de_fallo(accion: str, exc: BaseException) -> str:
    """Mensaje de error, con la receta del 403 cuando corresponde."""
    mensaje = f"{accion}: {exc}"
    return mensaje + _PISTA_403 if _es_403(exc) else mensaje


def _version_instalada() -> str:
    try:
        return importlib.metadata.version("edge-tts")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return ""


def _como_tupla(version: str) -> tuple[int, ...]:
    """«7.3.1» -> (7, 3, 1), para poder comparar versiones."""
    return tuple(int(parte) for parte in re.findall(r"\d+", version)[:3])


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

        instalada = _version_instalada()
        if instalada and _como_tupla(instalada) < _como_tupla(VERSION_MINIMA):
            raise ProveedorNoDisponible(
                f"La versión instalada de edge-tts ({instalada}) es anterior a "
                f"la {VERSION_MINIMA} y el servicio de Microsoft la rechaza con "
                f"un 403.\n"
                f'    pip install -U "edge-tts>={VERSION_MINIMA}"'
            )

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
                _mensaje_de_fallo(
                    "edge-tts no pudo generar el audio con la voz "
                    f"«{self.config.voz}»",
                    exc,
                )
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
                _mensaje_de_fallo("No se pudo consultar el catálogo de voces", exc)
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
