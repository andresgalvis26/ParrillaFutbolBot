# Documentacion Tecnica - ParrillaFutbolBot

Complemento tecnico al `README.md` principal del proyecto.

## Arquitectura

### Componentes

```
bot_parrilla.py (logica central)
    |-- FutbolRedScraper           # curl_cffi + BeautifulSoup
    |-- PartidosDeHoyScrapper      # requests + BeautifulSoup
    |-- FutbolEnVivoColombiaScrapper  # requests + BeautifulSoup (tablas)
    |-- get_scraper()              # Factory segun fuente/config
    |-- DateUtils                  # Formateo y parseo de fechas
    |-- Partido                    # Modelo de datos
    |-- DataFormatter              # Formateo a Markdown para Telegram
    |
    v
bot_local.py (hereda de bot_parrilla.py)
    |-- Importa get_scraper, DateUtils, DataFormatter, setup_logging
    |-- user_sources: Dict[int, str]  (fuente preferida por chat en memoria)
    |-- Application polling de python-telegram-bot
    |-- Handlers: comandos, botones inline, texto libre
    |-- Menu interactivo multi-paso: /start -> seleccion fuente -> menu principal
    |-- Menu interactivo multi-paso: /start -> seleccion fuente -> menu principal
```

### Flujo de scraping (ambos scripts)

```
1. get_scraper(source)  ->  FutbolRedScraper | PartidosDeHoyScrapper
2. scraper.obtener_partidos_hoy() | .obtener_partidos_manana() | .obtener_partidos_fecha()
3. DataFormatter.format_partidos()  ->  string en Markdown
4. Envio a Telegram (Bot.send_message) o impresion en consola (modo test)
```

### Seleccion de fuente

La funcion `get_scraper(source=None)` en `bot_parrilla.py` determina el scraper asi:

```python
def get_scraper(source=None):
    if source is None:
        source = os.getenv('SCRAPER_SOURCE', 'partidos-de-hoy')
    # 'futbolred'      -> FutbolRedScraper()
    # 'partidos-de-hoy' -> PartidosDeHoyScrapper()
    # 'futbolenvivo'    -> FutbolEnVivoColombiaScrapper()
```

## Scrapers

### FutbolRedScraper

- **URL**: `https://www.futbolred.com/parrilla-de-futbol`
- **Proteccion**: Akamai CDN (edgesuite.net) - bloquea `requests` normal con HTTP 403
- **Solucion**: `curl_cffi` con `impersonate='chrome120'` para imitar el fingerprint TLS de Chrome
- **Estructura HTML**:
  ```html
  <table>
    <tr><th class="partido">Viernes 10 de Julio</th><th>LIGA</th><th>HORA</th><th>CANAL</th></tr>
    <tr><td>Equipo A-Equipo B</td><td>Liga</td><td>Hora</td><td>Canal</td></tr>
  </table>
  ```
- Soporta multiples fechas: la pagina tiene una tabla por dia (tipicamente hoy y manana)

### PartidosDeHoyScrapper

- **URL principal**: `https://partidos-de-hoy.co`
- **URL calendario**: `https://partidos-de-hoy.co/calendario-de-partidos-en-colombia/` (fallback para fechas futuras)
- **Proteccion**: Sin CDN agresivo, funciona con `requests` normal
- **Estructura HTML**: WordPress con tabs `.scf-tab` y listas `.scf-match-list`
- La portada solo muestra el tab del dia actual en HTML (los demas se cargan via JS). El metodo `obtener_partidos_fecha()` consulta primero la portada y, si no encuentra datos para la fecha solicitada, hace fallback al calendario donde **si** estan todas las pestañas renderizadas en HTML (tipicamente 6-7 dias).
- **Parseo del calendario**: itera sobre pares `.scf-tab` / `.scf-tabpanel`, extrae la fecha de cada tab y asigna los partidos de su panel correspondiente.
- Soporta `obtener_partidos_manana()` y `obtener_partidos_fecha()` para fechas dentro del rango del calendario.

### FutbolEnVivoColombiaScrapper

- **URL**: `https://www.futbolenvivocolombia.com/`
- **Proteccion**: Sin CDN agresivo, funciona con `requests` normal
- **Estructura HTML**: Tablas `table.tablaPrincipal` con una por dia (~15 dias visibles en HTML)
  ```html
  <table class="tablaPrincipal">
    <tr class="cabeceraTabla"><td>Partidos de hoy viernes, 10/07/2026</td></tr>
    <tr class="cabeceraCompericion"><td>FIFA Copa Mundial 2026</td></tr>
    <tr>
      <td class="hora">14:00</td>
      <td class="local">España</td>
      <td class="visitante">Bélgica</td>
      <td class="canales">DSports</td>
    </tr>
  </table>
  ```
- La fecha se extrae con regex `(\d{1,2}/\d{1,2}/\d{4})` desde la cabecera de cada tabla.
- Soporta `obtener_partidos_manana()` y `obtener_partidos_fecha()` sin necesidad de fallback (todas las fechas estan en la misma pagina).
- Es la fuente que mas partidos aporta por dia (~20-30).

## Comandos CLI (bot_parrilla.py)

```bash
# Envio a Telegram
python bot_parrilla.py hoy                   # Partidos de hoy
python bot_parrilla.py manana                # Partidos de manana
python bot_parrilla.py semana                # Resumen semanal
python bot_parrilla.py todo                  # Hoy + manana

# Prueba en consola (sin enviar a Telegram)
python bot_parrilla.py test                  # Test hoy (default)
python bot_parrilla.py test manana           # Test manana
python bot_parrilla.py test semana           # Test semana

# Seleccion de fuente (con cualquier comando)
python bot_parrilla.py test --source futbolred
python bot_parrilla.py hoy --source partidos-de-hoy
```

## Dependencias

### Directas (src/config/requirements.txt)

```text
requests            # HTTP para partidos-de-hoy.co
beautifulsoup4      # Parseo HTML
python-telegram-bot # API de Telegram
python-dotenv       # Variables de entorno desde .env
curl_cffi           # HTTP con fingerprint TLS (Akamai bypass)
```

### Transitivas principales

- `requests` -> `urllib3`, `charset-normalizer`, `idna`, `certifi`
- `beautifulsoup4` -> `soupsieve`
- `python-telegram-bot` -> `httpx` -> `httpcore`, `h11`, `anyio`, `sniffio`, `certifi`, `idna`
- `curl_cffi` -> `cffi` -> `pycparser`, `certifi`, `rich` -> `markdown-it-py` -> `mdurl`, `pygments`, `typing-extensions`

## Banderas de paises

`config/emoji_ligas.py` contiene el diccionario `BANDERAS` que mapea nombres de paises
(en espanol e ingles) a sus banderas emoji. El metodo `Partido._agregar_banderas()`
parsea los nombres de los equipos (formato "Espana-Belgica" o "Spain VS Belgium"),
normaliza acentos y busca cada equipo en el diccionario. Si encuentra ambos,
muestra: `:flag_es:Espana  vs  :flag_be:Belgica`.

El diccionario incluye mas de 80 paises con sus variantes idiomaticas.

## Logs

`src/bot_parrilla.py` configura logging asi:

- Consola: siempre activo
- Archivo: `logs/bot_parrilla.log` (crea la carpeta `logs/` si no existe)
- Nivel: `INFO` por defecto (configurable via `LOG_LEVEL` en `.env`)
- Formato: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

## Notas tecnicas

- `bot_local.py` importa `get_scraper`, `DateUtils`, `DataFormatter` y `setup_logging` desde `bot_parrilla.py`. No duplica logica de scraping.
- La fuente se guarda por chat en memoria (`user_sources: Dict[int, str]`). Se pierde al reiniciar el bot.
- `bot_parrilla.py` expone `_filtrar_partidos_por_fecha()` como funcion de modulo para filtrar partidos por fecha en espanol.
- Los scripts `.bat` en `tests/` pueden estar desactualizados respecto a las rutas actuales.
- `src/main.py` no existe en el repositorio. Era parte de un flujo de produccion anterior con Flask que ya no se mantiene.
- Para cambiar la fuente en el bot interactivo, usa `/source` o la opcion "Cambiar Fuente" del menu.

## Zona horaria

Todo el bot opera en **Colombia (UTC-5)** independientemente de donde se ejecute:

```python
COL_TZ = timezone(timedelta(hours=-5))
```

Esto es esencial porque servicios como Render usan UTC por defecto. Sin esta correccion, `datetime.now()` devolveria el dia UTC y los comandos `/hoy`, `/manana` y `/semana` calcularian fechas incorrectas (tipicamente un dia adelantado para Colombia).

La constante `COL_TZ` se define en ambos scripts (`bot_parrilla.py` y `bot_local.py`) y todos los `datetime.now()` del proyecto usan `datetime.now(COL_TZ)`.
