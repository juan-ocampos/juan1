"""Interfaz de línea de comandos de Voceo."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from voceo import __version__, audio, config as modulo_config, generador
from voceo import plantillas as modulo_plantillas
from voceo import lote as modulo_lote
from voceo import proveedores
from voceo.config import Config
from voceo.errores import ErrorDePlantilla, VoceoError

EPILOGO = """\
Ejemplos:
  voceo generar "Atención, el centro comercial cierra en 15 minutos."
  voceo plantilla llamado_persona --campo nombre="Ana Martínez"
  voceo plantilla vehiculo --campo placas=ABC-123 --campo motivo="dejó las luces encendidas"
  voceo lote ejemplos/avisos_del_dia.csv -d audio/hoy
  voceo voces --buscar MX
  voceo lote avisos.csv --perfil echo -d salida/   (formato para equipos Echo)
  voceo validar salida/*.mp3 --kbps 96
  voceo web
  voceo doctor

Nota: los valores negativos necesitan «=» para que no se confundan con una
opción:  --velocidad=-10%   (o bien  --velocidad -10 , sin el símbolo %).
"""


# --- utilidades de presentación ------------------------------------------
def _escribir(mensaje: str = "") -> None:
    print(mensaje)


def _error(mensaje: str) -> None:
    print(f"✗ {mensaje}", file=sys.stderr)


def _mostrar_resultado(resultado: generador.Resultado) -> None:
    for aviso in resultado.avisos:
        _escribir(f"! {aviso}")
    _escribir(f"✓ {resultado.resumen()}")


# --- construcción de la configuración ------------------------------------
def _opciones_comunes(parser: argparse.ArgumentParser) -> None:
    grupo = parser.add_argument_group("ajustes de voz y audio")
    grupo.add_argument("--config", type=Path, metavar="RUTA",
                       help="archivo de configuración TOML (por defecto voceo.toml)")
    grupo.add_argument("--perfil", metavar="NOMBRE",
                       help="perfil definido en la configuración (p. ej. emergencia)")
    grupo.add_argument("--proveedor", choices=proveedores.nombres(),
                       help="motor de voz a usar")
    grupo.add_argument("--voz", metavar="ID",
                       help="voz del proveedor (ver: voceo voces)")
    grupo.add_argument("--velocidad", metavar="±N%%",
                       help="velocidad de lectura; usa --velocidad=-10%% para ir más lento")
    grupo.add_argument("--tono", metavar="±NHz", help="tono de la voz, p. ej. +5Hz")
    grupo.add_argument("--volumen", metavar="±N%%", help="volumen de la síntesis")
    grupo.add_argument("--repetir", type=int, metavar="N",
                       help="veces que se repite el mensaje")
    grupo.add_argument("--bitrate", metavar="N", help="calidad del MP3, p. ej. 192k")
    grupo.add_argument("--plantillas", type=Path, metavar="RUTA",
                       help="archivo TOML de plantillas")
    campanilla = grupo.add_mutually_exclusive_group()
    campanilla.add_argument("--campanilla", dest="campanilla", action="store_true",
                            default=None, help="anteponer el «din-don» de atención")
    campanilla.add_argument("--sin-campanilla", dest="campanilla", action="store_false",
                            help="no anteponer la campanilla")
    normalizar = grupo.add_mutually_exclusive_group()
    normalizar.add_argument("--normalizar", dest="normalizar_volumen",
                            action="store_true", default=None,
                            help="igualar el volumen de todos los avisos")
    normalizar.add_argument("--sin-normalizar", dest="normalizar_volumen",
                            action="store_false", help="no tocar el volumen")


#: Opciones de la CLI que corresponden una a una con un ajuste de `Config`.
_OPCIONES_DE_CONFIG = (
    "proveedor", "voz", "velocidad", "tono", "volumen", "repetir",
    "bitrate", "campanilla", "normalizar_volumen", "plantillas",
)


def _config_base(args: argparse.Namespace) -> Config:
    """Configuración del archivo TOML y del perfil, sin las opciones de la CLI."""
    return modulo_config.cargar(
        getattr(args, "config", None), getattr(args, "perfil", None)
    )


def _opciones_cli(args: argparse.Namespace) -> dict[str, object]:
    """Ajustes indicados explícitamente en la línea de órdenes."""
    return {
        nombre: getattr(args, nombre, None)
        for nombre in _OPCIONES_DE_CONFIG
        if getattr(args, nombre, None) is not None
    }


def _construir_config(args: argparse.Namespace) -> Config:
    """Configuración final: archivo < perfil < opciones de la línea de órdenes."""
    return _config_base(args).con(**_opciones_cli(args))


def _texto_de_entrada(valor: str) -> str:
    """Permite pasar el texto directamente, desde un archivo o por tubería."""
    if valor == "-":
        return sys.stdin.read()
    ruta = Path(valor)
    if len(valor) < 300 and ruta.suffix.lower() == ".txt" and ruta.is_file():
        return ruta.read_text(encoding="utf-8")
    return valor


def _destino(args: argparse.Namespace, config: Config, sugerencia: str) -> Path:
    from voceo.texto import nombre_de_archivo

    if args.salida:
        return Path(args.salida)
    return Path(config.salida) / f"{nombre_de_archivo(sugerencia)}.mp3"


# --- órdenes --------------------------------------------------------------
def _orden_generar(args: argparse.Namespace) -> int:
    config = _construir_config(args)
    entrada = _texto_de_entrada(args.texto)
    final = generador.preparar_texto(entrada, config)
    if args.simular:
        _escribir(final)
        return 0
    destino = _destino(args, config, final)
    _mostrar_resultado(generador.generar(final, destino, config))
    return 0


def _orden_plantilla(args: argparse.Namespace) -> int:
    config = _construir_config(args)
    plantilla = modulo_plantillas.obtener(args.nombre, config.plantillas)
    valores: dict[str, str] = {}
    for asignacion in args.campo or []:
        if "=" not in asignacion:
            raise VoceoError(
                f"«{asignacion}» debe tener la forma campo=valor, "
                'p. ej. --campo nombre="Ana Martínez"'
            )
        clave, valor = asignacion.split("=", 1)
        valores[clave.strip()] = valor.strip()

    if plantilla.ajustes:
        # La plantilla manda sobre la configuración, pero no sobre la CLI.
        config = modulo_config.aplicar(
            _config_base(args), plantilla.ajustes, f"plantilla {plantilla.nombre}"
        ).con(**_opciones_cli(args))
    try:
        contenido = plantilla.rellenar(valores)
    except ErrorDePlantilla as exc:
        if not exc.faltantes:
            raise
        ejemplo = " ".join(f"--campo {campo}=..." for campo in exc.faltantes)
        raise ErrorDePlantilla(f"{exc}\n  Añádelos así:  {ejemplo}") from exc
    final = generador.preparar_texto(contenido, config)
    if args.simular:
        _escribir(final)
        return 0
    destino = _destino(args, config, plantilla.nombre)
    _mostrar_resultado(generador.generar(final, destino, config))
    return 0


def _orden_plantillas(args: argparse.Namespace) -> int:
    config = _construir_config(args)
    catalogo = modulo_plantillas.cargar(config.plantillas)
    if args.nombre:
        plantilla = modulo_plantillas.obtener(args.nombre, config.plantillas)
        _escribir(f"{plantilla.nombre}: {plantilla.descripcion}")
        _escribir()
        _escribir(plantilla.texto)
        _escribir()
        for campo in plantilla.campos:
            defecto = plantilla.por_defecto.get(campo)
            marca = f" (por defecto: «{defecto}»)" if defecto is not None else " (obligatorio)"
            deletreo = "  [se deletrea]" if campo in plantilla.deletrear else ""
            _escribir(f"  --campo {campo}=...{marca}{deletreo}")
        if plantilla.ajustes:
            ajustes = ", ".join(f"{k}={v}" for k, v in plantilla.ajustes.items())
            _escribir(f"\nAjustes propios: {ajustes}")
        return 0

    ancho = max((len(n) for n in catalogo), default=0)
    for nombre, plantilla in catalogo.items():
        obligatorios = ", ".join(plantilla.obligatorios)
        detalle = f"  (pide: {obligatorios})" if obligatorios else ""
        _escribir(f"  {nombre.ljust(ancho)}  {plantilla.descripcion}{detalle}")
    _escribir(f"\n{len(catalogo)} plantillas en {config.plantillas}")
    _escribir(
        "Para personalizarlas, copia ese archivo y usa  "
        "--plantillas mis_avisos.toml"
    )
    return 0


def _orden_lote(args: argparse.Namespace) -> int:
    config = _construir_config(args)
    carpeta = Path(args.carpeta) if args.carpeta else Path(config.salida)

    if args.simular:
        for numero, fila in enumerate(modulo_lote.leer_csv(Path(args.csv)), start=1):
            if not any(fila.values()):
                continue
            config_fila = modulo_lote.config_de_fila(config, fila, numero)
            contenido = modulo_lote.texto_de_fila(fila, config_fila, config.plantillas)
            _escribir(
                f"{numero:02d}. {generador.preparar_texto(contenido, config_fila)}"
            )
        return 0

    resumen = modulo_lote.procesar(
        Path(args.csv),
        carpeta,
        config,
        sobrescribir=args.sobrescribir,
        al_empezar=lambda numero, nombre: _escribir(f"  [{numero:02d}] {nombre}"),
    )
    _escribir()
    for resultado in resumen.generados:
        _escribir(f"✓ {resultado.resumen()}")
    for omitido in resumen.omitidos:
        _escribir(f"= ya existía, se omitió: {omitido} (usa --sobrescribir)")
    for fallo in resumen.fallidos:
        _error(f"fila {fallo.numero} ({fallo.archivo}): {fallo.error}")
    _escribir(
        f"\n{len(resumen.generados)} generados, {len(resumen.omitidos)} omitidos, "
        f"{len(resumen.fallidos)} con error."
    )
    if resumen.generados:
        _escribir(f"Manifiesto: {carpeta / 'manifiesto.csv'}")
    return 1 if resumen.fallidos else 0


def _orden_voces(args: argparse.Namespace) -> int:
    config = _construir_config(args)
    proveedor = proveedores.obtener(config.proveedor, config)
    proveedor.verificar()
    catalogo = proveedor.voces(None if args.idioma == "todos" else args.idioma)
    if args.buscar:
        aguja = args.buscar.lower()
        catalogo = [
            v for v in catalogo
            if aguja in v.id.lower() or aguja in v.nombre.lower()
            or aguja in v.descripcion.lower()
        ]
    if not catalogo:
        _escribir("No se encontraron voces con ese criterio.")
        return 0
    ancho = max(len(v.id) for v in catalogo)
    for voz in catalogo:
        extra = f"  {voz.genero}" if voz.genero else ""
        descripcion = f"  {voz.descripcion}" if voz.descripcion else ""
        _escribir(f"  {voz.id.ljust(ancho)}{extra}{descripcion}")
    _escribir(f"\n{len(catalogo)} voces  ·  proveedor: {proveedor.nombre}")
    _escribir(f'Úsala con:  voceo generar "..." --voz {catalogo[0].id}')
    return 0


def _orden_campanilla(args: argparse.Namespace) -> int:
    destino = Path(args.salida or "campanilla.wav")
    audio.generar_campanilla(destino)
    _escribir(f"✓ {destino}  (úsala con  campanilla_archivo = \"{destino}\"  en voceo.toml)")
    return 0


def _orden_validar(args: argparse.Namespace) -> int:
    """Revisa MP3 ya generados contra el formato que exigen los reproductores."""
    rutas: list[Path] = []
    for patron in args.archivos:
        ruta = Path(patron)
        rutas.extend(sorted(ruta.parent.glob(ruta.name)) if "*" in patron else [ruta])
    if not rutas:
        raise VoceoError("No se encontró ningún archivo que revisar.")

    fallidos = 0
    for ruta in rutas:
        revision = audio.comprobar_mp3(ruta, kbps_esperado=args.kbps)
        marca = "✓" if revision.valido else "✗"
        detalle = f"  {revision.kbps:.0f} kbit/s" if revision.kbps else ""
        _escribir(f"{marca} {ruta.name}{detalle}")
        for problema in revision.problemas:
            _escribir(f"    {problema}")
        fallidos += not revision.valido

    _escribir(f"\n{len(rutas) - fallidos} de {len(rutas)} correctos.")
    return 1 if fallidos else 0


def _orden_web(args: argparse.Namespace) -> int:
    """Levanta la aplicación web en este equipo."""
    try:
        from voceo.web import crear_app
    except ImportError as exc:
        raise VoceoError(
            "Falta la dependencia «flask» para la aplicación web:\n"
            "    pip install \".[web]\""
        ) from exc

    config = _construir_config(args)
    app = crear_app(config)
    anfitrion = "0.0.0.0" if args.publico else "127.0.0.1"  # noqa: S104
    _escribir(f"Voceo web en  http://localhost:{args.puerto}")
    if args.publico:
        _escribir("Accesible desde la red local.")
    if not os.environ.get("VOCEO_CLAVE"):
        _escribir("Sin contraseña. Para exigir una:  export VOCEO_CLAVE=\"...\"")
    _escribir("Para un servidor de verdad usa gunicorn (ver el README).")
    _escribir("Ctrl+C para parar.")
    app.run(host=anfitrion, port=args.puerto)
    return 0


def _orden_doctor(args: argparse.Namespace) -> int:
    config = _construir_config(args)
    _escribir(f"voceo {__version__}   ·   Python {sys.version.split()[0]}")
    _escribir()

    ruta = next((r for r in modulo_config.rutas_de_busqueda() if r.is_file()), None)
    _escribir(f"Configuración : {ruta or 'valores por defecto (no hay voceo.toml)'}")
    perfiles = modulo_config.perfiles_disponibles(getattr(args, "config", None))
    _escribir(f"Perfiles      : {', '.join(perfiles) or 'ninguno'}")

    programa = audio.ruta_ffmpeg()
    _escribir(f"ffmpeg        : {programa or 'NO ENCONTRADO'}")
    if not programa:
        _escribir("                sin ffmpeg no hay campanilla, repeticiones ni")
        _escribir("                normalización. Instala: pip install imageio-ffmpeg")

    try:
        catalogo = modulo_plantillas.cargar(config.plantillas)
        _escribir(f"Plantillas    : {len(catalogo)} en {config.plantillas}")
    except VoceoError as exc:
        _escribir(f"Plantillas    : {exc}")

    _escribir()
    _escribir("Proveedores de voz:")
    for nombre in proveedores.nombres():
        marca = "→" if nombre == config.proveedor else " "
        try:
            proveedores.obtener(nombre, config).verificar()
            estado = "listo"
        except VoceoError as exc:
            estado = str(exc).splitlines()[0]
        _escribir(f" {marca} {nombre.ljust(11)} {estado}")
        _escribir(f"     {proveedores.DESCRIPCIONES.get(nombre, '')}")
    return 0


# --- analizador de argumentos --------------------------------------------
def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voceo",
        description="Convierte texto en audio MP3 con voz natural para el "
                    "voceo de un centro comercial.",
        epilog=EPILOGO,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"voceo {__version__}")
    ordenes = parser.add_subparsers(dest="orden", metavar="ORDEN")

    generar = ordenes.add_parser(
        "generar", help="genera un MP3 a partir de un texto",
        description="Genera un MP3 a partir de un texto suelto. Acepta también "
                    "la ruta de un .txt o «-» para leer de la entrada estándar.",
    )
    generar.add_argument("texto", help="el aviso, un archivo .txt o «-»")
    generar.add_argument("-o", "--salida", metavar="ARCHIVO.mp3",
                         help="archivo de salida")
    generar.add_argument("--simular", action="store_true",
                         help="muestra el texto final sin generar audio")
    _opciones_comunes(generar)
    generar.set_defaults(funcion=_orden_generar)

    plantilla = ordenes.add_parser(
        "plantilla", help="genera un MP3 a partir de una plantilla",
        description="Rellena una plantilla de aviso y genera el MP3.",
    )
    plantilla.add_argument("nombre", help="nombre de la plantilla")
    plantilla.add_argument("--campo", action="append", metavar="CLAVE=VALOR",
                           help="valor para un hueco de la plantilla (repetible)")
    plantilla.add_argument("-o", "--salida", metavar="ARCHIVO.mp3",
                           help="archivo de salida")
    plantilla.add_argument("--simular", action="store_true",
                           help="muestra el texto final sin generar audio")
    _opciones_comunes(plantilla)
    plantilla.set_defaults(funcion=_orden_plantilla)

    listado = ordenes.add_parser(
        "plantillas", help="lista las plantillas disponibles",
        description="Lista las plantillas o muestra el detalle de una.",
    )
    listado.add_argument("nombre", nargs="?", help="ver el detalle de una plantilla")
    _opciones_comunes(listado)
    listado.set_defaults(funcion=_orden_plantillas)

    lote = ordenes.add_parser(
        "lote", help="genera muchos avisos desde un CSV",
        description="Genera un MP3 por cada fila de un CSV exportado de una "
                    "hoja de cálculo.",
    )
    lote.add_argument("csv", help="archivo CSV con los avisos")
    lote.add_argument("-d", "--carpeta", help="carpeta de salida")
    lote.add_argument("--sobrescribir", action="store_true",
                      help="regenerar los audios que ya existan")
    lote.add_argument("--simular", action="store_true",
                      help="muestra los textos finales sin generar audio")
    _opciones_comunes(lote)
    lote.set_defaults(funcion=_orden_lote)

    voces = ordenes.add_parser(
        "voces", help="lista las voces del proveedor",
        description="Lista las voces disponibles en el proveedor configurado.",
    )
    voces.add_argument("--idioma", default="es",
                       help="prefijo de idioma (es, es-MX, en… o «todos»)")
    voces.add_argument("--buscar", help="filtrar por texto")
    _opciones_comunes(voces)
    voces.set_defaults(funcion=_orden_voces)

    campanilla = ordenes.add_parser(
        "campanilla", help="genera el archivo de campanilla (WAV)",
        description="Genera el «din-don» de atención por si quieres escucharlo "
                    "o editarlo.",
    )
    campanilla.add_argument("-o", "--salida", metavar="ARCHIVO.wav")
    campanilla.set_defaults(funcion=_orden_campanilla)

    validar = ordenes.add_parser(
        "validar", help="revisa que unos MP3 cumplan el formato exigido",
        description="Comprueba que los MP3 empiecen directamente en el audio "
                    "(sin ID3 ni cabecera Xing por delante) y que el bitrate "
                    "cuadre. Para reproductores empotrados exigentes.",
    )
    validar.add_argument("archivos", nargs="+", metavar="ARCHIVO.mp3")
    validar.add_argument("--kbps", type=int, default=None,
                         help="bitrate esperado, p. ej. 96")
    validar.set_defaults(funcion=_orden_validar)

    web = ordenes.add_parser(
        "web", help="levanta la aplicación web en este equipo",
        description="Abre la página desde la que se generan los avisos con el "
                    "navegador. Pensada para pruebas locales; en un servidor, "
                    "usa gunicorn.",
    )
    web.add_argument("--puerto", type=int, default=8080, help="puerto (8080)")
    web.add_argument("--publico", action="store_true",
                     help="permitir el acceso desde otros equipos de la red")
    _opciones_comunes(web)
    web.set_defaults(funcion=_orden_web)

    doctor = ordenes.add_parser(
        "doctor", help="comprueba la instalación y la configuración",
        description="Revisa ffmpeg, las plantillas y los proveedores de voz.",
    )
    _opciones_comunes(doctor)
    doctor.set_defaults(funcion=_orden_doctor)

    return parser


def main(argumentos: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argumentos)
    if not getattr(args, "funcion", None):
        parser.print_help()
        return 0
    try:
        return args.funcion(args)
    except VoceoError as exc:
        _error(str(exc))
        return 1
    except KeyboardInterrupt:
        _error("interrumpido")
        return 130
    except BrokenPipeError:
        # Pasa al encadenar con `| head`: el otro extremo cierra la tubería
        # antes de que terminemos de escribir. No es un fallo del programa;
        # se redirige la salida al vacío para que Python no se queje al salir.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
