"""Servidor web de Voceo.

Una página donde el personal del centro comercial escribe el aviso (o elige
una plantilla), lo escucha y se descarga el MP3. El archivo se genera, se
entrega y se descarta: el servidor no guarda nada.
"""

from __future__ import annotations

import csv
import io
import os
import secrets
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
)
from werkzeug.exceptions import HTTPException

from voceo import __version__, audio, generador, lote as modulo_lote
from voceo import config as modulo_config
from voceo import plantillas as modulo_plantillas
from voceo import proveedores
from voceo import texto as modulo_texto
from voceo.config import Config
from voceo.errores import VoceoError

#: Voces en español que funcionan bien por megafonía. Se muestran de entrada;
#: la lista completa se carga con /voces si hay conexión.
VOCES_RECOMENDADAS = [
    {"id": "es-MX-DaliaNeural", "nombre": "Dalia — México (femenina)"},
    {"id": "es-MX-JorgeNeural", "nombre": "Jorge — México (masculina)"},
    {"id": "es-ES-ElviraNeural", "nombre": "Elvira — España (femenina)"},
    {"id": "es-ES-AlvaroNeural", "nombre": "Álvaro — España (masculina)"},
    {"id": "es-CO-SalomeNeural", "nombre": "Salomé — Colombia (femenina)"},
    {"id": "es-AR-ElenaNeural", "nombre": "Elena — Argentina (femenina)"},
]

#: Topes para que un uso descuidado no dispare el gasto ni el tiempo de espera.
MAXIMO_CARACTERES = 5000
MAXIMO_FILAS_CSV = 200
MAXIMO_SUBIDA = 2 * 1024 * 1024  # 2 MB

def _config_inicial() -> Config:
    """Configuración del servidor: la del archivo TOML que indique el entorno."""
    ruta = os.environ.get("VOCEO_CONFIG", "").strip()
    return modulo_config.cargar(Path(ruta) if ruta else None)


def _sin_autorizar() -> Response:
    return Response(
        "Acceso restringido.",
        401,
        {"WWW-Authenticate": 'Basic realm="Voceo"'},
    )


def _ajustes_del_formulario(config: Config, datos: dict[str, Any]) -> Config:
    """Aplica a la configuración lo que el usuario eligió en la página.

    Todo lo que llega del navegador es texto sin garantías, así que un valor
    absurdo se convierte en un error explicado, nunca en un fallo del servidor.
    """
    cambios: dict[str, Any] = {}
    if datos.get("voz"):
        cambios["voz"] = str(datos["voz"])
    if datos.get("velocidad") not in (None, ""):
        cambios["velocidad"] = str(datos["velocidad"])
    if datos.get("repetir") not in (None, ""):
        try:
            cambios["repetir"] = max(1, min(int(datos["repetir"]), 3))
        except (TypeError, ValueError):
            raise VoceoError(
                f"«{datos['repetir']}» no es un número de repeticiones válido."
            ) from None
    try:
        cambios["campanilla"] = modulo_config.a_bool(datos.get("campanilla", False))
    except ValueError:
        raise VoceoError("El valor de la campanilla debe ser sí o no.") from None
    return config.con(**cambios)


def _texto_solicitado(datos: dict[str, Any], config: Config) -> str:
    """El texto del aviso: el escrito a mano o el de la plantilla elegida."""
    if datos.get("plantilla"):
        plantilla = modulo_plantillas.obtener(str(datos["plantilla"]), config.plantillas)
        campos = datos.get("campos") or {}
        valores = {
            clave: str(valor)
            for clave, valor in campos.items()
            if clave in plantilla.campos and str(valor).strip()
        }
        return plantilla.rellenar(valores)
    contenido = str(datos.get("texto", "")).strip()
    if not contenido:
        raise VoceoError("Escribe el texto del aviso o elige una plantilla.")
    if len(contenido) > MAXIMO_CARACTERES:
        raise VoceoError(
            f"El texto es demasiado largo ({len(contenido)} caracteres; "
            f"el máximo es {MAXIMO_CARACTERES})."
        )
    return contenido


def crear_app(config: Config | None = None) -> Flask:
    """Crea la aplicación Flask.

    Args:
        config: ajustes a usar; si no se indica, se leen del archivo TOML que
            señale la variable `VOCEO_CONFIG` (o los valores de fábrica).
    """
    app = Flask(
        __name__,
        template_folder="plantillas_html",
        static_folder="estaticos",
        static_url_path="/estaticos",
    )
    app.config["MAX_CONTENT_LENGTH"] = MAXIMO_SUBIDA
    app.config["VOCEO"] = config or _config_inicial()
    # El catálogo de voces tarda unos segundos en consultarse: se cachea aquí.
    app.config["VOCES"] = []
    clave = os.environ.get("VOCEO_CLAVE", "").strip()

    @app.before_request
    def _exigir_clave():
        """Protege el sitio con una contraseña si `VOCEO_CLAVE` está definida."""
        if not clave or request.path == "/salud":
            return None
        credenciales = request.authorization
        # Se comparan bytes: `compare_digest` rechaza las cadenas con acentos
        # o eñes, y una contraseña en español los lleva a menudo.
        recibida = (credenciales.password or "") if credenciales else ""
        if secrets.compare_digest(recibida.encode("utf-8"), clave.encode("utf-8")):
            return None
        return _sin_autorizar()

    @app.errorhandler(VoceoError)
    def _error_esperado(exc: VoceoError):
        return jsonify({"error": str(exc)}), 400

    @app.errorhandler(413)
    def _archivo_enorme(_):
        return jsonify({"error": "El archivo es demasiado grande (máximo 2 MB)."}), 413

    @app.errorhandler(Exception)
    def _error_inesperado(exc: Exception):
        """Último recinto: nada de páginas de error en crudo.

        El detalle va al registro del servidor, no al navegador, y el usuario
        recibe un mensaje que puede repetir a quien administre el servicio.
        """
        if isinstance(exc, HTTPException):
            return exc
        app.logger.exception("Fallo inesperado atendiendo %s", request.path)
        return (
            jsonify(
                {
                    "error": "Error interno del servidor. Vuelve a intentarlo; "
                    "si sigue fallando, revisa el registro del servicio."
                }
            ),
            500,
        )

    # --- páginas ---------------------------------------------------------
    @app.get("/")
    def inicio():
        actual: Config = app.config["VOCEO"]
        catalogo = modulo_plantillas.cargar(actual.plantillas)
        return render_template(
            "index.html",
            version=__version__,
            config=actual,
            voces=VOCES_RECOMENDADAS,
            hay_ffmpeg=audio.ruta_ffmpeg() is not None,
            plantillas=[
                {
                    "nombre": p.nombre,
                    "descripcion": p.descripcion,
                    "campos": list(p.campos),
                    "obligatorios": list(p.obligatorios),
                    "por_defecto": p.por_defecto,
                    "deletrear": list(p.deletrear),
                }
                for p in catalogo.values()
            ],
        )

    @app.get("/salud")
    def salud():
        return jsonify({"estado": "ok", "version": __version__})

    @app.get("/voces")
    def voces():
        """Catálogo completo de voces del proveedor, cacheado en memoria."""
        if not app.config["VOCES"]:
            actual: Config = app.config["VOCEO"]
            proveedor = proveedores.obtener(actual.proveedor, actual)
            proveedor.verificar()
            app.config["VOCES"] = [
                {
                    "id": v.id,
                    "nombre": f"{v.id}  ({v.genero})" if v.genero else v.id,
                }
                for v in proveedor.voces("es")
            ]
        return jsonify(app.config["VOCES"])

    # --- generación ------------------------------------------------------
    @app.post("/previsualizar")
    def previsualizar():
        """Devuelve el texto tal y como lo va a leer la voz, sin generar audio."""
        datos = request.get_json(silent=True) or {}
        actual = _ajustes_del_formulario(app.config["VOCEO"], datos)
        contenido = _texto_solicitado(datos, actual)
        return jsonify({"texto": generador.preparar_texto(contenido, actual)})

    @app.post("/generar")
    def generar():
        """Genera un aviso y devuelve el MP3."""
        datos = request.get_json(silent=True) or {}
        actual = _ajustes_del_formulario(app.config["VOCEO"], datos)
        contenido = _texto_solicitado(datos, actual)

        nombre = str(datos.get("archivo", "")).strip()
        base = modulo_texto.nombre_de_archivo(
            nombre or str(datos.get("plantilla") or contenido)
        )
        with tempfile.TemporaryDirectory(prefix="voceo-web-") as temporal:
            resultado = generador.generar(contenido, Path(temporal) / f"{base}.mp3", actual)
            datos_mp3 = resultado.ruta.read_bytes()
            duracion = resultado.duracion or 0.0

        respuesta = send_file(
            io.BytesIO(datos_mp3),
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name=f"{base}.mp3",
        )
        # El navegador usa estas cabeceras para mostrar el resumen.
        respuesta.headers["X-Voceo-Duracion"] = f"{duracion:.1f}"
        respuesta.headers["X-Voceo-Archivo"] = f"{base}.mp3"
        return respuesta

    @app.post("/lote")
    def generar_lote():
        """Recibe un CSV y devuelve un ZIP con todos los avisos."""
        archivo = request.files.get("csv")
        if archivo is None or not archivo.filename:
            raise VoceoError("Adjunta el archivo CSV con los avisos.")
        actual = _ajustes_del_formulario(app.config["VOCEO"], request.form.to_dict())

        with tempfile.TemporaryDirectory(prefix="voceo-lote-") as temporal:
            carpeta = Path(temporal)
            entrada = carpeta / "avisos.csv"
            archivo.save(entrada)

            filas = modulo_lote.leer_csv(entrada)
            if len(filas) > MAXIMO_FILAS_CSV:
                raise VoceoError(
                    f"El CSV tiene {len(filas)} filas; el máximo por tanda es "
                    f"{MAXIMO_FILAS_CSV}. Divídelo en varios archivos."
                )

            salida = carpeta / "avisos"
            resumen = modulo_lote.procesar(entrada, salida, actual, sobrescribir=True)
            if not resumen.generados:
                detalle = "; ".join(f.error for f in resumen.fallidos[:3])
                raise VoceoError(f"No se pudo generar ningún aviso. {detalle}")

            memoria = io.BytesIO()
            with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as comprimido:
                for resultado in resumen.generados:
                    comprimido.write(resultado.ruta, resultado.ruta.name)
                comprimido.write(salida / "manifiesto.csv", "manifiesto.csv")
                if resumen.fallidos:
                    informe = io.StringIO()
                    escritor = csv.writer(informe)
                    escritor.writerow(["fila", "archivo", "error"])
                    for fallo in resumen.fallidos:
                        escritor.writerow([fallo.numero, fallo.archivo, fallo.error])
                    comprimido.writestr("errores.csv", informe.getvalue())
        memoria.seek(0)

        respuesta = send_file(
            memoria,
            mimetype="application/zip",
            as_attachment=True,
            download_name="avisos.zip",
        )
        respuesta.headers["X-Voceo-Generados"] = str(len(resumen.generados))
        respuesta.headers["X-Voceo-Fallidos"] = str(len(resumen.fallidos))
        return respuesta

    return app


# Punto de entrada para gunicorn:  gunicorn "voceo.web.app:crear_app()"
if __name__ == "__main__":  # pragma: no cover - solo para desarrollo
    crear_app().run(host="127.0.0.1", port=8080, debug=True)
