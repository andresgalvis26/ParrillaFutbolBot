# ParrillaFutbolBot

Bot de Telegram para consultar y enviar parrillas de partidos de futbol.

Dos modos de ejecucion:

- `src/bot_local.py`: bot interactivo de Telegram por `polling`
- `src/bot_parrilla.py`: script de ejecucion puntual para enviar mensajes o imagenes a un `CHAT_ID`

Ambos scripts comparten la misma logica de scraping y seleccion de fuente de datos.

## Fuentes De Datos

El proyecto soporta dos fuentes intercambiables:

| Fuente | URL | Tecnologia | Estado |
|--------|-----|-----------|--------|
| `futbolred` | futbolred.com | `curl_cffi` (bypass Akamai CDN) | ✅ |
| `partidos-de-hoy` | partidos-de-hoy.co | `requests` | ✅ |
| `futbolenvivo` | futbolenvivocolombia.com | `requests` | ✅ |

La fuente se selecciona en este orden de precedencia:

1. **Bot interactivo**: selección por botón al usar `/start` o `/source` (por chat)
2. **Script CLI**: parametro `--source`
3. Variable de entorno `SCRAPER_SOURCE` en `config/.env`
4. Default: `partidos-de-hoy`

## Estructura Del Proyecto

```text
ParrillaFutbolBot/
|-- .github/
|   `-- workflows/
|       `-- parrilla.yml          # Cron diario en GitHub Actions
|-- assets/
|-- docs/
|-- src/
|   |-- bot_local.py              # Bot interactivo por polling
|   |-- bot_parrilla.py           # Script de envio puntual
|   |-- image_generator.py        # Genera la imagen PNG de la parrilla
|   |-- config/
|   |   |-- .env                  # Variables de entorno (no versionado)
|   |   |-- .env.example          # Ejemplo de configuracion
|   |   |-- __init__.py
|   |   |-- emoji_ligas.py        # Emojis por liga
|   |   `-- requirements.txt      # Dependencias (unico source de verdad)
|   `-- logs/                     # Logs de ejecucion (creados automaticamente)
|-- tests/
|   |-- run_bot_local.bat
|   |-- run_bot_parrilla.bat
|   `-- run_bot_parrilla_with_test_hoy.bat
`-- README.md
```

## Requisitos

- Python 3.8+
- Un bot de Telegram con `BOT_TOKEN`
- Un `CHAT_ID` si vas a usar el modo de envio automatico

## Instalacion

1. Clona el repositorio:

```bash
git clone https://github.com/andresgalvis26/ParrillaFutbolBot.git
cd ParrillaFutbolBot
```

2. Crea un entorno virtual (opcional pero recomendado):

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instala dependencias:

```bash
pip install -r src/config/requirements.txt
```

4. Crea el archivo `src/config/.env` a partir de `src/config/.env.example`:

```env
BOT_TOKEN=tu_bot_token_aqui
CHAT_ID=tu_chat_id_aqui
WEBHOOK_URL=https://tu-dominio.com

# Fuente de datos: 'futbolred', 'partidos-de-hoy' o 'futbolenvivo' (default)
SCRAPER_SOURCE=partidos-de-hoy

LOG_LEVEL=INFO
```

## Banderas De Paises

Los partidos entre selecciones nacionales muestran automaticamente la bandera de cada pais:

```
🌍 *🇪🇸España  vs  🇧🇪Bélgica*
   🏆 Mundial 2026
   🕐 2:00 p. m.
   📺 DSports
```

El mapeo de paises a banderas esta en `src/config/emoji_ligas.py` (diccionario `BANDERAS`).
Soporta nombres en espanol e ingles con mas de 80 paises.

## Como Usarlo

### Modo Bot Interactivo (recomendado)

```bash
cd src
python bot_local.py
```

Comandos disponibles: `/start`, `/hoy`, `/manana`, `/semana`, `/source`, `/status`, `/help`

Tambien responde a texto libre como `partidos`, `hoy`, `manana`, `semana`, `fuente`, `ayuda`, `status`.

El bot guía al usuario con un menú interactivo: al iniciar (`/start`) pregunta la fuente de datos (`futbolred`, `partidos-de-hoy` o `futbolenvivo`), luego muestra el menú principal con botones para Hoy, Mañana, Semana, Cambiar Fuente y Ayuda.

### Modo Script / Envio Puntual

```bash
cd src
python bot_parrilla.py hoy
python bot_parrilla.py manana
python bot_parrilla.py semana
python bot_parrilla.py todo          # hoy + manana
python bot_parrilla.py test          # prueba en consola (no envia Telegram)
python bot_parrilla.py test manana   # prueba de manana en consola
```

### Seleccionar Fuente

```bash
python bot_parrilla.py hoy --source futbolred
python bot_parrilla.py test --source partidos-de-hoy
python bot_parrilla.py semana --source futbolenvivo
```

El `--source` se puede usar con cualquier comando (`hoy`, `manana`, `semana`, `todo`, `test`).
Fuentes disponibles: `futbolred`, `partidos-de-hoy`, `futbolenvivo`.

### Formato De Envio

En local, por defecto se envia el mensaje de texto de siempre. Tambien puedes generar una imagen PNG con la parrilla:

```bash
python bot_parrilla.py hoy --format imagen
python bot_parrilla.py hoy --format ambos
python bot_parrilla.py manana --source futbolenvivo --format imagen
```

- `mensaje`: solo texto.
- `imagen`: una o varias imagenes PNG con los partidos, paginadas cada 8.
- `ambos`: manda primero el texto y luego las imagenes. Es el default del workflow de GitHub Actions y del cron diario.

Las imagenes se generan con Pillow, sin navegador. En GitHub Actions se elige con el input `formato` al hacer **Run workflow**; el cron diario usa `ambos` (texto + imagen).

Para `semana`, el formato imagen manda una o varias imagenes por cada dia con partidos, asi que puede enviar bastante contenido. Para el uso normal, `hoy` o `manana` es suficiente.

## Como Funciona Cada Script

### `src/bot_parrilla.py`

- Entrypoint principal para logica de scraping y formateo
- Usa `python-telegram-bot` solo para el envio del mensaje
- `FutbolRedScraper`: usa `curl_cffi` para evitar el bloqueo de Akamai CDN
- `PartidosDeHoyScrapper`: usa `requests` normal (fallback a calendario para fechas futuras)
- `FutbolEnVivoColombiaScrapper`: usa `requests`, ~15-30 partidos/dia, ~15 dias visibles
- `get_scraper()`: factory que retorna el scraper segun la fuente configurada
- `image_generator.py`: genera la imagen PNG con Pillow (sin navegador) y pagina cada 8 partidos
- `--format mensaje|imagen|ambos`: elige que enviar; el default del CLI es `mensaje` y el del workflow es `ambos`
- Pensado para cron jobs o ejecuciones programadas
- Escribe logs en consola y en `logs/bot_parrilla.log`

### `src/bot_local.py`

- Bot interactivo que corre de manera continua por polling
- Importa y delega la logica de scraping a `bot_parrilla.py` (get_scraper, DateUtils, DataFormatter, setup_logging)
- Usa `python-telegram-bot` con botones inline y comandos
- Menu interactivo multi-paso: `/start` pregunta la fuente, luego muestra menu con botones
- La fuente se guarda **por chat en memoria** (`user_sources`). Se elige con `/source` o desde el menu.
- Orden de resolucion de fuente: preferencia del usuario > `SCRAPER_SOURCE` en `.env` > `partidos-de-hoy`

## Dependencias

`src/config/requirements.txt` contiene solo las 6 dependencias directas:

```text
requests
beautifulsoup4
python-telegram-bot
python-dotenv
curl_cffi
Pillow
```

Las dependencias transitivas (httpx, rich, cffi, soupsieve, etc.) se instalan automaticamente via pip.

## Logs

`src/bot_parrilla.py` crea la carpeta `logs/` y escribe `logs/bot_parrilla.log` ademas de la salida por consola.

## Automatizacion

### GitHub Actions (recomendado, $0)

El workflow `.github/workflows/parrilla.yml` ejecuta el bot todos los dias a las **8:00 AM Colombia (13:00 UTC)** y envia **texto + imagen**. Tambien se puede lanzar a mano desde **Actions -> Parrilla Futbol -> Telegram -> Run workflow**.

Configura estos secretos en el repositorio (**Settings -> Secrets and variables -> Actions**):

- `BOT_TOKEN`: token del bot de Telegram.
- `CHAT_ID`: chat o grupo destino.

El workflow instala `src/config/requirements.txt` y ejecuta:

```bash
cd src
python bot_parrilla.py hoy --source futbolred --format ambos
```

Desde la ejecucion manual puedes elegir `hoy`, `manana`, `semana` o `todo`, la fuente (`futbolred`, `partidos-de-hoy` o `futbolenvivo`) y el formato (`mensaje`, `imagen` o `ambos`). El cron programado usa `hoy`, `futbolred` y `ambos`. Para cambiar la hora del cron, edita la linea `cron` del workflow (GitHub usa UTC; Colombia es UTC-5).

Costo: GitHub Free incluye 2,000 minutos Linux al mes en repos privados. Una corrida diaria consume aproximadamente 1-2 minutos.

### Ejecucion manual / cron local

```bash
cd src
python bot_parrilla.py hoy --source futbolred
python bot_parrilla.py hoy --source futbolenvivo
```

En Windows:

```bash
cd /d D:\ruta\al\proyecto\src && python bot_parrilla.py hoy --source futbolred
cd /d D:\ruta\al\proyecto\src && python bot_parrilla.py hoy --source futbolenvivo
```

El cron diario de Render ya no es necesario: GitHub Actions lo reemplaza sin costo.

## Zona Horaria

El bot opera en hora **Colombia (UTC-5)**. Todos los `datetime.now()` usan `datetime.now(timezone(timedelta(hours=-5)))` para que funcione correctamente desde cualquier servidor (Render usa UTC, por ejemplo).

## Notas

- `src/main.py` no existe. La documentacion historica mencionaba un modo de produccion con Flask que ya no esta en el codigo.
- Los scripts `.bat` en `tests/` pueden estar desactualizados respecto a las rutas actuales.
- Si la fuente `futbolred` falla, verifica que `curl_cffi` este correctamente instalado.
- La fuente `partidos-de-hoy` muestra el dia actual en portada; los demas dias se resuelven via `calendario-de-partidos-en-colombia/` que tiene las pestañas con todas las fechas en HTML.
- La fuente `futbolred` soporta varios dias (tablas separadas por fecha en la misma pagina).
- La fuente `futbolenvivo` es la que mas partidos trae (~15-30 por dia, ~15 dias visibles). Usa `tablaPrincipal` con filas por competicion y partido.

## Recomendacion De Uso

```bash
cd src
python bot_local.py
```
