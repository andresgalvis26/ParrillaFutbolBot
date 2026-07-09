# ParrillaFutbolBot

Bot de Telegram para consultar y enviar parrillas de partidos de futbol.

El repositorio hoy tiene dos modos distintos de ejecucion y no un unico flujo unificado:

- `src/bot_local.py`: bot interactivo de Telegram por `polling`
- `src/bot_parrilla.py`: script de ejecucion puntual para enviar mensajes a un `CHAT_ID`

## Estado Actual

Este README describe el estado real del proyecto hoy, incluyendo limitaciones conocidas.

- El modo mas confiable hoy es `src/bot_local.py`
- `src/bot_parrilla.py` existe y se puede ejecutar, pero no todos sus comandos estan igual de consistentes
- La documentacion anterior mencionaba `src/main.py`, pero ese archivo no existe en el repo actual
- Los dos scripts no usan exactamente la misma fuente de datos

## Estructura Real Del Proyecto

```text
ParrillaFutbolBot/
|-- assets/
|-- docs/
|-- src/
|   |-- bot_local.py
|   |-- bot_parrilla.py
|   `-- config/
|       |-- .env.example
|       |-- __init__.py
|       |-- emoji_ligas.py
|       `-- requirements.txt
|-- tests/
|   |-- run_bot_local.bat
|   |-- run_bot_parrilla.bat
|   `-- run_bot_parrilla_with_test_hoy.bat
`-- requirements.txt
```

## Fuentes De Datos Actuales

Hoy el proyecto no usa una sola fuente de datos de forma uniforme:

- `src/bot_local.py` consulta `https://www.futbolred.com/parrilla-de-futbol`
- `src/bot_parrilla.py` usa `https://partidos-de-hoy.co` para el modo `hoy`
- `src/bot_parrilla.py` tambien conserva un scraper para `FutbolRed`, pero no esta integrado de forma consistente en todos los comandos

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

2. Crea un entorno virtual opcional:

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Instala dependencias:

```bash
pip install -r requirements.txt
```

4. Crea el archivo `src/config/.env` a partir de `src/config/.env.example`:

```env
BOT_TOKEN=tu_bot_token_aqui
CHAT_ID=tu_chat_id_aqui
WEBHOOK_URL=https://tu-dominio.com
FLASK_PORT=10000
DEBUG=False
LOG_LEVEL=INFO
```

## Importante Sobre Las Rutas

Los dos scripts cargan variables asi:

```python
load_dotenv('config/.env')
```

Eso significa que hoy lo mas coherente es ejecutarlos desde la carpeta `src`, no desde la raiz del repo.

## Como Levantarlo Hoy

### Modo Recomendado: Bot Interactivo

Desde la raiz del repo:

```bash
cd src
python bot_local.py
```

Que hace este modo:

- levanta un bot de Telegram por `polling`
- responde a comandos y mensajes de texto
- consulta partidos bajo demanda
- devuelve informacion formateada en el chat

Comandos disponibles en este modo:

- `/start`
- `/partidos`
- `/hoy`
- `/manana`
- `/semana`
- `/status`
- `/help`

Tambien intenta responder a texto libre como `partidos`, `hoy`, `manana`, `semana`, `ayuda` y `status`.

### Modo Script / Envio Puntual

Desde la raiz del repo:

```bash
cd src
python bot_parrilla.py hoy
```

Otros comandos implementados:

```bash
cd src
python bot_parrilla.py manana
python bot_parrilla.py semana
python bot_parrilla.py todo
python bot_parrilla.py test hoy
python bot_parrilla.py test manana
python bot_parrilla.py test semana
```

Que hace este modo:

- genera un mensaje con partidos
- envia el mensaje al `CHAT_ID` configurado
- en modo `test`, imprime el resultado en consola sin enviar a Telegram

## Como Funciona Cada Script

### `src/bot_local.py`

- usa `python-telegram-bot`
- hace scraping de `FutbolRed`
- formatea partidos con emojis por liga
- ofrece botones inline y comandos de Telegram
- corre de manera continua hasta que lo detengas

### `src/bot_parrilla.py`

- usa `python-telegram-bot` solo para el envio del mensaje
- ejecuta scraping y formateo de forma puntual
- esta pensado para cron jobs o ejecuciones programadas
- escribe logs en consola y, si puede, tambien en `logs/bot_parrilla.log`

## Limitaciones Y Problemas Conocidos

Estos puntos reflejan el estado real actual del codigo:

1. `src/main.py` no existe.
   La documentacion historica mencionaba un modo produccion con Flask, pero hoy ese archivo no esta en el repositorio.

2. `src/bot_parrilla.py` no esta completamente consistente en todos sus modos.
   Dentro de `obtener_partidos()`, el modo `hoy` inicializa `PartidosDeHoyScrapper()`, pero los modos `manana` y `semana` referencian `scraper` sin inicializar. En el estado actual, esos comandos pueden fallar.

3. Las fuentes de datos no estan unificadas.
   `bot_local.py` y `bot_parrilla.py` no consultan exactamente el mismo sitio ni siguen el mismo flujo.

4. Los scripts `.bat` bajo `tests/` parecen desactualizados.
   Hoy hacen `cd` a la carpeta `tests` y luego intentan ejecutar `python src/...`, pero esa ruta no existe relativa a `tests`.

5. La automatizacion documentada antes como flujo estable de produccion ya no coincide totalmente con el estado del repo.

## Automatizacion

El proyecto parece haber sido pensado para ejecuciones programadas de `bot_parrilla.py`, pero con el estado actual hay que tomarlo como un flujo parcialmente funcional, no como un despliegue estable ya validado.

Si quieres automatizar el modo hoy, el comando objetivo seria algo como:

```bash
cd /ruta/al/proyecto/src && python bot_parrilla.py hoy
```

En Windows, el equivalente seria ejecutar el script desde `src`.

## Dependencias

Las dependencias actuales estan duplicadas en:

- `requirements.txt`
- `src/config/requirements.txt`

Ambos archivos hoy contienen el mismo listado principal, incluyendo:

- `python-telegram-bot`
- `requests`
- `beautifulsoup4`
- `python-dotenv`
- `flask`

## Recomendacion De Uso Hoy

Si solo quieres levantar el proyecto y probarlo con la menor friccion posible, usa:

```bash
cd src
python bot_local.py
```

Ese es el camino mas consistente con el codigo actual.
