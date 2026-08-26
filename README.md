# Voceo — avisos en MP3 con voz natural para centros comerciales

Convierte texto en archivos **MP3 listos para la megafonía**: campanilla de
atención, voz neuronal en español, silencios, repeticiones y todos los avisos
al mismo volumen.

```bash
voceo generar "Atención, señores visitantes. El centro comercial cierra en quince minutos."
# ✓ audio/atencion-senores-visitantes-el-centro-com.mp3  ·  11.2 s  ·  edge/es-MX-DaliaNeural
```

- **Voz natural en español** (México, España, Colombia, Argentina…) sin pagar
  nada ni registrarse, con las voces neuronales de Microsoft Edge.
- **Plantillas** para los avisos de siempre: llamado a una persona, menor
  extraviado, vehículo con las luces encendidas, cierre, promociones, evacuación…
- **Generación por lotes** desde un CSV exportado de Excel: la lista de avisos
  del día se convierte en una carpeta de MP3.
- **Producción pensada para megafonía**: «din-don» de atención, mensaje repetido,
  volumen normalizado y MP3 mono, que es lo que esperan los amplificadores.
- **Cuatro motores de voz** intercambiables, uno de ellos sin internet.

---

## Instalación

Requiere **Python 3.11 o superior**.

```bash
git clone https://github.com/juan-ocampos/juan1.git
cd juan1
pip install -e .[ffmpeg]
```

`ffmpeg` es lo que monta el aviso (campanilla, silencios, repeticiones,
normalización). El extra `[ffmpeg]` instala una copia lista para usar; si
prefieres el del sistema:

```bash
sudo apt install ffmpeg     # Debian / Ubuntu
brew install ffmpeg         # macOS
winget install Gyan.FFmpeg  # Windows
```

Comprueba que todo está en su sitio:

```bash
voceo doctor
```

> Sin ffmpeg el programa sigue generando la voz en MP3, pero avisa de que
> omitió la campanilla, las repeticiones y la normalización.

---

## Uso

### Un aviso suelto

```bash
voceo generar "Atención. Se solicita personal de limpieza en el área de comidas."
voceo generar "Buenas tardes." -o audio/saludo.mp3
voceo generar aviso.txt                 # el texto desde un archivo
cat aviso.txt | voceo generar -         # o desde una tubería
voceo generar "..." --simular           # ver el texto final sin gastar audio
```

### Con una plantilla

```bash
voceo plantillas                        # ver las 14 plantillas incluidas
voceo plantillas vehiculo               # ver los campos de una

voceo plantilla llamado_persona --campo nombre="Ana Martínez" --campo lugar="caja 3"
voceo plantilla vehiculo --campo placas=ABC-123 --campo color=gris --campo modelo=sedán
voceo plantilla cierre_proximo --campo minutos=quince
```

Las placas se leen letra a letra automáticamente: *«placas a, be, ce, guion,
uno, dos, tres»*, que por altavoz se entiende mucho mejor que «abecé ciento
veintitrés».

### Muchos avisos de una vez

Prepara la lista en una hoja de cálculo, expórtala a CSV y:

```bash
voceo lote ejemplos/avisos_del_dia.csv -d audio/hoy
```

```csv
archivo,plantilla,texto,nombre,tienda,promocion,minutos,repetir
bienvenida.mp3,bienvenida,,,,,,
llamado-ana.mp3,llamado_persona,,Ana Martínez,,,,
promo-zapateria.mp3,promocion,,,Calzado del Centro,el dos por uno en dama,,
aviso-libre.mp3,,"El estacionamiento cuenta con vigilancia las 24 horas.",,,,,
cierre-15.mp3,cierre_proximo,,,,,quince,2
```

- `texto` **o** `plantilla` (una de las dos por fila).
- Las columnas `proveedor`, `voz`, `velocidad`, `tono`, `volumen`, `repetir`,
  `campanilla`… cambian los ajustes **solo de esa fila**.
- Cualquier otra columna rellena un campo de la plantilla.
- Si una fila falla, las demás se generan igual y al final se listan los errores.
- Se escribe un `manifiesto.csv` con qué audio corresponde a qué texto.

### Elegir la voz

```bash
voceo voces                      # todas las voces en español
voceo voces --buscar MX          # solo las mexicanas
voceo generar "Hola" --voz es-ES-ElviraNeural
```

Voces que funcionan bien para megafonía: `es-MX-DaliaNeural` (la de fábrica),
`es-MX-JorgeNeural`, `es-ES-ElviraNeural`, `es-CO-SalomeNeural`,
`es-AR-ElenaNeural`.

---

## Configuración

Copia `voceo.ejemplo.toml` como `voceo.toml` en la carpeta desde la que
trabajas (o en `~/.config/voceo/voceo.toml`):

```toml
proveedor = "edge"
voz = "es-MX-DaliaNeural"
velocidad = "-5%"          # negativo = más lento, se entiende mejor
salida = "audio"
campanilla = true
repetir = 1
normalizar_volumen = true

[perfiles.emergencia]
velocidad = "-15%"
repetir = 2
volumen = "+15%"
```

Un **perfil** es un juego de ajustes que se activa cuando hace falta:

```bash
voceo plantilla evacuacion --perfil emergencia
```

La precedencia es: **opciones de la línea de órdenes** > ajustes de la
plantilla > perfil > `voceo.toml` > valores de fábrica.

> Los valores negativos necesitan `=` para que la terminal no los confunda con
> una opción: `--velocidad=-10%` (o bien `--velocidad -10`, sin el `%`).

---

## Escribir los avisos

Dos marcas ayudan a que el texto suene bien por altavoz:

| Marca | Efecto |
|---|---|
| `[pausa]` | un silencio breve; `[pausa:2]` lo alarga |
| `[deletrear:ABC-123]` | se lee letra a letra: *a, be, ce, guion, uno, dos, tres* |

Además, las abreviaturas se expanden solas: `Sr.` → *señor*, `mód.` → *módulo*,
`Av.` → *avenida*, `20%` → *20 por ciento*, `dto.` → *descuento*.

### Plantillas propias

Copia el archivo de plantillas que trae el programa (su ruta la muestra
`voceo plantillas`), edítalo y úsalo:

```bash
voceo plantilla mi_aviso --plantillas mis_avisos.toml --campo tienda="Zapatería"
```

```toml
[mi_aviso]
descripcion = "Aviso propio del centro"
campos = ["tienda", "nivel"]
texto = """
Atención. {tienda}, en {nivel}, los espera con sus nuevas promociones.
"""
[mi_aviso.por_defecto]
nivel = "planta baja"
[mi_aviso.ajustes]
repetir = 2
```

---

## Motores de voz

| Proveedor | Calidad | Coste | Internet | Cómo se activa |
|---|---|---|---|---|
| `edge` *(por defecto)* | muy buena | gratis | sí | ya viene instalado |
| `openai` | excelente, admite instrucciones de estilo | de pago | sí | `pip install -e .[openai]` + `OPENAI_API_KEY` |
| `elevenlabs` | la mejor | de pago | sí | `pip install -e .[elevenlabs]` + `ELEVENLABS_API_KEY` |
| `piper` | buena | gratis | **no** | `pip install -e .[piper]` + un modelo `.onnx` |

```bash
export OPENAI_API_KEY="..."
voceo generar "Bienvenidos" --proveedor openai --voz nova
```

`piper` es la opción para un equipo sin salida a internet: descarga una voz en
español de [piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/es)
y apunta a ella con `--voz /ruta/es_MX-voz.onnx`.

---

## Cómo suena un aviso

```
[0.4 s de silencio] din–don [0.35 s] «Atención, señores visitantes…» [1.0 s]
```

Con `--repetir 2` el mensaje se repite con una pausa en medio, y con
`normalizar_volumen` todos los avisos salen a la misma sonoridad (−16 LUFS),
para no tener que tocar el amplificador entre uno y otro.

La campanilla se genera por software; para escucharla o cambiarla:

```bash
voceo campanilla -o campanilla.wav
# y en voceo.toml:  campanilla_archivo = "campanilla.wav"
```

---

## Órdenes disponibles

| Orden | Para qué sirve |
|---|---|
| `voceo generar TEXTO` | un aviso a partir de un texto, un `.txt` o `-` |
| `voceo plantilla NOMBRE` | un aviso a partir de una plantilla |
| `voceo plantillas [NOMBRE]` | listar las plantillas o ver una en detalle |
| `voceo lote CSV` | generar todos los avisos de un CSV |
| `voceo voces` | ver las voces del proveedor |
| `voceo campanilla` | generar el archivo de la campanilla |
| `voceo doctor` | revisar instalación, ffmpeg, plantillas y proveedores |

Todas admiten `--simular` (donde tiene sentido) para ver el texto final sin
generar audio.

---

## Problemas frecuentes

**«ffmpeg no está instalado»** — `pip install imageio-ffmpeg`, o instálalo desde
el gestor de paquetes del sistema.

**«edge-tts no pudo generar el audio»** — casi siempre es la red. Si el centro
comercial usa un proxy, exporta `HTTPS_PROXY`; si además inspecciona el tráfico
HTTPS, indica el certificado de la empresa con `VOCEO_CA_BUNDLE=/ruta/ca.crt`.

**El aviso se entiende mal por los altavoces** — baja la velocidad
(`--velocidad=-12%`), sube las repeticiones (`--repetir 2`) y usa `[pausa]`
entre las frases importantes.

**Números o siglas mal leídos** — enciérralos en `[deletrear:...]` o escríbelos
con palabras («quince» en vez de «15»).

---

## Desarrollo

```bash
pip install -e .[dev,ffmpeg]
pytest
```

Las pruebas no llaman a ningún servicio externo: usan un proveedor de mentira
que genera tonos, y las que necesitan ffmpeg se saltan solas si no está.

Estructura:

```
voceo/
  cli.py            órdenes de la línea de órdenes
  config.py         ajustes, archivo TOML y perfiles
  texto.py          normalización del texto (abreviaturas, deletreo, pausas)
  plantillas.py     plantillas de avisos
  generador.py      texto -> proveedor -> audio
  audio.py          campanilla, silencios, repeticiones y MP3 (ffmpeg)
  lote.py           generación desde CSV
  proveedores/      edge, openai, elevenlabs, piper
  datos/            plantillas incluidas
```

## Licencia

MIT — ver [LICENSE](LICENSE).
