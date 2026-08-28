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
- **Aplicación web opcional**, para que el personal genere sus avisos desde el
  navegador sin instalar nada.

---

## Instalación

Requiere **Python 3.10 o superior**. Compruébalo antes de nada:

```bash
python3 --version
```

Si es menor (macOS trae la 3.9 de fábrica), instala una versión moderna:
`brew install python@3.12` en macOS, `sudo apt install python3.12-venv` en
Debian/Ubuntu, o desde [python.org](https://www.python.org/downloads/).

```bash
git clone https://github.com/juan-ocampos/juan1.git
cd juan1
python3 -m venv .venv
source .venv/bin/activate          # Windows:  .venv\Scripts\activate
pip install --upgrade pip
pip install ".[ffmpeg]"
```

Las comillas hacen falta en zsh (el intérprete de macOS), que si no se come
los corchetes. Y `pip` tiene que ser razonablemente reciente: las versiones
antiguas no entienden un proyecto sin `setup.py`.

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
| `openai` | excelente, admite instrucciones de estilo | de pago | sí | `pip install ".[openai]"` + `OPENAI_API_KEY` |
| `elevenlabs` | la mejor | de pago | sí | `pip install ".[elevenlabs]"` + `ELEVENLABS_API_KEY` |
| `piper` | buena | gratis | **no** | `pip install ".[piper]"` + un modelo `.onnx` |

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
| `voceo validar` | comprobar que unos MP3 cumplen el formato exigido |
| `voceo web` | levantar la aplicación web en este equipo |
| `voceo doctor` | revisar instalación, ffmpeg, plantillas y proveedores |

Todas admiten `--simular` (donde tiene sentido) para ver el texto final sin
generar audio.

---

## Formato de salida para reproductores exigentes

Los reproductores empotrados no son todos iguales. Algunos —como los equipos
de voceo de estacionamiento del proyecto **Echo**— no saben saltarse las
cabeceras: esperan que el **primer byte del archivo sea ya audio**. Si el MP3
empieza por `ID3`, el decodificador se pone a buscar el sincronismo byte a
byte, con el resultado que uno se imagina.

Para eso está el perfil `echo`, que viene de fábrica:

```bash
voceo lote avisos.csv --perfil echo -d salida/
voceo validar salida/*.mp3 --kbps 96
```

Produce **MP3 mono, 44.100 Hz, 96 kbit/s CBR, sin ID3 y sin cabecera
Xing/Info**, y añade una compresión con limitador para que la voz se imponga
al ruido de motores.

Los ajustes que lo componen se pueden usar sueltos:

| Ajuste | Qué hace |
|---|---|
| `id3 = false` | no escribe etiquetas: el archivo empieza en la primera trama |
| `xing = false` | quita la cabecera Xing/Info del principio |
| `compresor = true` | añade `acompressor` + `alimiter` para entornos ruidosos |
| `bitrate = "96k"` | bitrate **constante**; con `-q:a` saldría variable |

### La comprobación

Cuando se pide `id3 = false` o `xing = false`, el programa **revisa el archivo
que acaba de escribir** antes de darlo por bueno, y falla si no cumple. Y se
puede revisar cualquier MP3 a mano, venga de donde venga:

```bash
$ voceo validar audio/*.mp3 --kbps 96
✓ cierre-15.mp3  96 kbit/s
✗ viejo.mp3  98 kbit/s
    empieza con una etiqueta ID3

1 de 2 correctos.
```

Devuelve código de salida 1 si alguno falla, así que sirve para encadenarlo en
un script.

Comprueba tres cosas: que no haya `ID3` delante, que los dos primeros bytes
sean un sincronismo MPEG válido, y que no haya cabecera Xing/Info —esta última
mirando el desplazamiento exacto donde iría, porque LAME escribe su versión en
los datos auxiliares de cada trama y buscar la cadena a ciegas daría falsos
positivos. Con `--kbps` comprueba además que el tamaño cuadre con ese bitrate
(unos 12 KB por segundo a 96 kbit/s).

> Un apunte para quien venga de usar `lame` directamente: el ejecutable de LAME
> siempre escribe la cabecera Info/Xing y no tiene forma de omitirla, así que
> hay que limpiarla después. ffmpeg sí puede evitarla de entrada
> (`-write_xing 0`), que es lo que hace este programa.

---

## Aplicación web

Para que el personal del centro comercial genere sus propios avisos sin
instalar nada y sin depender de un ordenador concreto, hay una página web con
lo mismo que la terminal: escribir el aviso o elegir una plantilla, escucharlo
y descargar el MP3.

```bash
pip install ".[web]"
export VOCEO_CLAVE="la-contraseña-del-centro"   # opcional pero recomendable
voceo web
```

Y se abre <http://localhost:8080>. Con `--publico` queda accesible desde los
demás equipos de la red local.

El servidor **no guarda nada**: genera el audio, lo entrega y lo descarta. No
hay base de datos ni carpeta de archivos que vigilar. Y no reproduce nada: los
MP3 se descargan y se copian al equipo de megafonía, que sigue sin necesitar
internet.

La página tiene dos pestañas: **Un aviso** (uno suelto, con reproductor para
escucharlo antes de descargar) y **Varios (CSV)** (sube el CSV y baja un ZIP
con todos los MP3 y el manifiesto). En «Ajustes de voz» se elige también el
**formato de salida**, incluido el de los equipos Echo.

### Ponerla en un servidor

La imagen de Docker lleva ffmpeg dentro y arranca con gunicorn:

```bash
docker build -t voceo .
docker run -p 8080:8080 -e VOCEO_CLAVE="la-contraseña" voceo
```

### En Google Cloud Run

Es el sitio natural: se apaga solo cuando nadie lo usa, así que con este
volumen de uso el coste es prácticamente cero.

```bash
gcloud config set project TU-PROYECTO
gcloud run deploy voceo \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "VOCEO_CLAVE=la-contraseña-del-centro" \
  --memory 512Mi \
  --timeout 300
```

`gcloud` compila el `Dockerfile`, sube la imagen y devuelve la URL. La primera
vez pedirá permiso para habilitar Cloud Build y Artifact Registry.

`--allow-unauthenticated` deja la URL abierta a internet, y quien protege la
página es `VOCEO_CLAVE` (una contraseña compartida, que el navegador pide al
entrar). Si el personal tiene cuentas de Google de la organización, la
alternativa más estricta es `--no-allow-unauthenticated` y dar el rol
*Cloud Run Invoker* a cada uno.

### Ajustes por entorno

| Variable | Para qué |
|---|---|
| `VOCEO_CLAVE` | contraseña de acceso; sin ella la página queda abierta |
| `VOCEO_CONFIG` | ruta a un `voceo.toml` con la voz y los ajustes por defecto |
| `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` | si el servidor usa esos motores |
| `PORT` | puerto donde escucha (Cloud Run lo pone solo) |

Topes de seguridad: 5.000 caracteres por aviso, 200 filas por CSV y 2 MB de
subida, para que un descuido no dispare el gasto ni el tiempo de espera.

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
pip install -e ".[dev,ffmpeg]"
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
  web/              aplicación web (Flask) y su página
  datos/            plantillas incluidas
  lector_toml.py    lectura de TOML compatible con Python 3.10
```

## Licencia

MIT — ver [LICENSE](LICENSE).
