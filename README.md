# ParrillaFutbolBot

Bot de Telegram para consultar y enviar parrillas de partidos de futbol.

Dos modos de ejecucion:

- `src/bot_local.py`: bot interactivo de Telegram por `polling`
- `src/bot_parrilla.py`: script de ejecucion puntual para enviar mensajes a un `CHAT_ID`

Ambos scripts comparten la misma logica de scraping y seleccion de fuente de datos.

## Fuentes De Datos

El proyecto soporta dos fuentes intercambiables:

| Fuente | URL | Tecnologia | Estado |
|--------|-----|-----------|--------|
| `futbolred` | futbolred.com | `curl_cffi` (bypass Akamai CDN) | ✅ |
| `partidos-de-hoy` | partidos-de-hoy.co | `requests` | ✅ |

La fuente se selecciona en este orden de precedencia:

1. **Bot interactivo**: selección por botón al usar `/start` o `/source` (por chat)
2. **Script CLI**: parametro `--source`
3. Variable de entorno `SCRAPER_SOURCE` en `config/.env`
4. Default: `partidos-de-hoy`

## Estructura Del Proyecto

```text
ParrillaFutbolBot/
|-- assets/
|-- docs/
|-- src/
|   |-- bot_local.py              # Bot interactivo por polling
|   |-- bot_parrilla.py           # Script de envio puntual
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
.venv\Scripts\activate
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

# Fuente de datos: 'futbolred' o 'partidos-de-hoy' (default)
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

El bot guía al usuario con un menú interactivo: al iniciar (`/start`) pregunta la fuente de datos, luego muestra el menú principal con botones para Hoy, Mañana, Semana, Cambiar Fuente y Ayuda.

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
```

El `--source` se puede usar con cualquier comando (`hoy`, `manana`, `semana`, `todo`, `test`).

## Como Funciona Cada Script

### `src/bot_parrilla.py`

- Entrypoint principal para logica de scraping y formateo
- Usa `python-telegram-bot` solo para el envio del mensaje
- `FutbolRedScraper`: usa `curl_cffi` para evitar el bloqueo de Akamai CDN
- `PartidosDeHoyScrapper`: usa `requests` normal
- `get_scraper()`: factory que retorna el scraper segun la fuente configurada
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

`src/config/requirements.txt` contiene solo las 5 dependencias directas:

```text
requests
beautifulsoup4
python-telegram-bot
python-dotenv
curl_cffi
```

Las dependencias transitivas (httpx, rich, cffi, soupsieve, etc.) se instalan automaticamente via pip.

## Logs

`src/bot_parrilla.py` crea la carpeta `logs/` y escribe `logs/bot_parrilla.log` ademas de la salida por consola.

## Automatizacion

Para ejecuciones programadas (cron / tareas programadas):

```bash
cd /ruta/al/proyecto/src && python bot_parrilla.py hoy --source futbolred
```

En Windows:

```bash
cd /d D:\ruta\al\proyecto\src && python bot_parrilla.py hoy
```

## Notas

- `src/main.py` no existe. La documentacion historica mencionaba un modo de produccion con Flask que ya no esta en el codigo.
- Los scripts `.bat` en `tests/` pueden estar desactualizados respecto a las rutas actuales.
- Si la fuente `futbolred` falla, verifica que `curl_cffi` este correctamente instalado.
- La fuente `partidos-de-hoy` muestra el dia actual en portada; los demas dias se resuelven via `calendario-de-partidos-en-colombia/` que tiene las pestañas con todas las fechas en HTML.
- La fuente `futbolred` soporta varios dias (tablas separadas por fecha en la misma pagina).

## Recomendacion De Uso

```bash
cd src
python bot_local.py
```
