"""
Módulo principal del bot de partidos de fútbol.

Extrae partidos desde dos fuentes posibles:
  - 'futbolred':       FutbolRed.com (usa curl_cffi para bypass de Akamai CDN)
  - 'partidos-de-hoy': Partidos-de-hoy.co (más estable, usando requests)

La fuente se selecciona por este orden de precedencia:
  1. Parámetro CLI:  --source futbolred|partidos-de-hoy
  2. Variable de entorno:  SCRAPER_SOURCE (config/.env)
  3. Default:  'partidos-de-hoy' (lo que está en producción)

Uso CLI:
  python bot_parrilla.py test [hoy|manana|semana] [--source futbolred|partidos-de-hoy]
  python bot_parrilla.py hoy|manana|semana|todo [--source fuente]
"""

import requests
from bs4 import BeautifulSoup
from telegram import Bot
import asyncio
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging
from typing import List, Dict, Optional
from config.emoji_ligas import EMOJI_LIGAS

# curl_cffi: librería que imita el fingerprint TLS de Chrome para evitar
# el bloqueo de Akamai CDN (edgesuite.net) en futbolred.com
from curl_cffi import requests as curl_requests

# Cargar variables de entorno desde un archivo .env
load_dotenv("config/.env")

# === CONFIGURACIÓN ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL = "https://www.futbolred.com/parrilla-de-futbol"

# Fuentes disponibles y default
SCRAPER_SOURCES = ["futbolred", "partidos-de-hoy"]
DEFAULT_SOURCE = os.getenv("SCRAPER_SOURCE", "partidos-de-hoy")


# Configurar logging de manera más robusta
def setup_logging():
    """Configura el sistema de logging"""
    # Crear directorio de logs si no existe
    log_dir = "logs"
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Configurar handlers
        handlers = [logging.StreamHandler()]  # Siempre consola

        # Intentar agregar archivo si es posible
        try:
            file_handler = logging.FileHandler(
                "logs/bot_parrilla.log", encoding="utf-8"
            )
            handlers.append(file_handler)
        except Exception as e:
            print(f"No se pudo crear archivo de log: {e}")

        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers,
        )

    except Exception as e:
        # Si todo falla, usar solo consola
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        print(f"Configuración de logging simplificada: {e}")


# Inicializar logging
setup_logging()
logger = logging.getLogger("ParrillaCronBot")

# === CLASES Y UTILIDADES MEJORADAS ===


class DateUtils:
    """Utilidades para manejo de fechas.

    Convierte fechas entre formatos inglés/español para
    comparar con las fechas que aparecen en las páginas web.
    """

    MESES_ES: Dict[str, str] = {
        "January": "enero",
        "February": "febrero",
        "March": "marzo",
        "April": "abril",
        "May": "mayo",
        "June": "junio",
        "July": "julio",
        "August": "agosto",
        "September": "septiembre",
        "October": "octubre",
        "November": "noviembre",
        "December": "diciembre",
    }

    # Inverso: nombre español -> inglés
    MESES_EN: Dict[str, str] = {v: k for k, v in MESES_ES.items()}

    # Abreviaturas de meses en inglés para parsear fechas como "10 Jul 2026"
    MESES_ABR: Dict[str, str] = {
        "jan": "January",
        "feb": "February",
        "mar": "March",
        "apr": "April",
        "may": "May",
        "jun": "June",
        "jul": "July",
        "aug": "August",
        "sep": "September",
        "oct": "October",
        "nov": "November",
        "dec": "December",
    }

    @classmethod
    def get_fecha_es(cls, fecha: datetime = None) -> str:
        """Obtiene la fecha en formato español: '10 de julio'"""
        if fecha is None:
            fecha = datetime.now()

        dia = str(fecha.day)
        mes = cls.MESES_ES[fecha.strftime("%B")]
        return f"{dia} de {mes}"

    @classmethod
    def get_hoy(cls) -> str:
        """Obtiene la fecha de hoy en español"""
        return cls.get_fecha_es()

    @classmethod
    def get_manana(cls) -> str:
        """Obtiene la fecha de mañana en español"""
        manana = datetime.now() + timedelta(days=1)
        return cls.get_fecha_es(manana)

    @classmethod
    def parse_fecha_partidos_de_hoy(cls, texto: str) -> Optional[str]:
        """Parsea una fecha como '10 Jul 2026' y devuelve '10 de julio'.

        Usado por PartidosDeHoyScrapper para extraer la fecha
        de los tabs o del texto de cada partido.
        """
        import re

        # Busca patrón: "10 Jul 2026" (día, mes abreviado, año)
        match = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", texto)
        if not match:
            return None

        dia, mes_abr, anio = match.groups()
        mes_completo = cls.MESES_ABR.get(mes_abr.lower(), mes_abr)
        mes_es = cls.MESES_ES.get(mes_completo, mes_completo)
        return f"{int(dia)} de {mes_es}"


class Partido:
    """Modelo de datos para un partido de fútbol.

    Almacena equipos, liga, hora, canal y fecha,
    y formatea el mensaje para Telegram con emojis.
    """

    def __init__(
        self,
        equipos: str,
        liga: str,
        hora: str,
        canal: str,
        fecha: Optional[str] = None,
    ):
        self.equipos = equipos
        self.liga = liga
        self.hora = hora
        self.canal = canal
        self.fecha = fecha
        self.emoji_liga = self._get_emoji_liga(liga)

    def _get_emoji_liga(self, liga: str) -> str:
        """Obtiene emoji según la liga, buscando en EMOJI_LIGAS (config/emoji_ligas.py)"""
        liga_lower = liga.lower()

        for emoji, keywords in EMOJI_LIGAS.items():
            for keyword in keywords:
                if keyword in liga_lower:
                    return emoji

        return "⚽"

    def to_markdown(self) -> str:
        """Convierte el partido a formato markdown con el estilo visual mejorado"""
        return f"{self.emoji_liga} *{self.equipos}*\n   \U0001f3c6 {self.liga}\n   \U0001f550 {self.hora}\n   \U0001f4fa {self.canal}\n"


class FutbolRedScraper:
    """Scraper para futbolred.com

    La página https://www.futbolred.com/parrilla-de-futbol muestra una tabla
    por cada día con partidos en formato:
      <table>
        <tr><th class="partido">Viernes 10 de Julio</th><th>LIGA</th><th>HORA</th><th>CANAL</th></tr>
        <tr><td>Equipo A-Equipo B</td><td>Liga</td><td>Hora</td><td>Canal</td></tr>
        ...
      </table>

    NOTA: Usa curl_cffi en lugar de requests porque futbolred.com está
    protegido por Akamai CDN (edgesuite.net) que bloquea las requests
    normales con HTTP 403. curl_cffi imita el fingerprint TLS de un
    navegador Chrome real para evadir el bloqueo.
    """

    def __init__(self):
        self.url = URL
        self.date_utils = DateUtils()
        # Sesión curl_cffi con headers de navegador real
        self.session = curl_requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                "Referer": "https://www.futbolred.com/",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def obtener_partidos_fecha(self, fecha_es: str) -> List[Partido]:
        """Obtiene partidos para una fecha específica (formato español: '10 de julio').

        1. Hace GET a la página con curl_cffi (impersonate='chrome120')
        2. Busca todas las tablas <table>
        3. Para cada tabla, la primera fila tiene la fecha
        4. Si la fecha coincide con la buscada, extrae los partidos
        """
        try:
            logger.info(f"Obteniendo partidos para: {fecha_es}")

            # curl_cffi con impersonate='chrome120' para imitar TLS de Chrome 120
            # y evitar el bloqueo de Akamai CDN
            response = self.session.get(self.url, impersonate="chrome120", timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            tablas = soup.find_all("table")
            partidos = []

            logger.info(f"Encontradas {len(tablas)} tablas en la página")

            for i, tabla in enumerate(tablas):
                filas = tabla.find_all("tr")
                if not filas:
                    continue

                # Verificar si la tabla corresponde a la fecha buscada
                primera_fila = filas[0]
                # La primera fila puede tener <th> o <td>, pero get_text funciona igual
                fecha_texto = primera_fila.get_text(strip=True).lower()

                logger.debug(f"Tabla {i + 1}: {fecha_texto[:50]}...")

                # Verificación más flexible de fecha
                if self._fecha_coincide(fecha_es, fecha_texto):
                    logger.info(f"Fecha encontrada en tabla {i + 1}: {fecha_texto}")

                    # Procesar partidos de esta tabla (saltar la fila de encabezado)
                    partidos_tabla = self._procesar_tabla(filas[1:], fecha_es)
                    partidos.extend(partidos_tabla)

                    logger.info(
                        f"Encontrados {len(partidos_tabla)} partidos en esta tabla"
                    )

            logger.info(
                f"Total de partidos encontrados para {fecha_es}: {len(partidos)}"
            )
            return partidos

        except requests.RequestException as e:
            logger.error(f"Error de conexión: {e}")
            return []
        except Exception as e:
            logger.error(f"Error inesperado obteniendo partidos: {e}")
            return []

    def _fecha_coincide(self, fecha_buscada: str, fecha_texto: str) -> bool:
        """Verifica si las fechas coinciden con mayor flexibilidad.

        Compara en minúsculas y también verifica por partes (día y mes)
        para tolerar diferencias en el formato.
        """
        fecha_buscada_lower = fecha_buscada.lower()
        fecha_texto_lower = fecha_texto.lower()

        # Verificación directa
        if fecha_buscada_lower in fecha_texto_lower:
            return True

        # Verificación por partes (día y mes)
        partes_buscada = fecha_buscada_lower.split(" de ")
        if len(partes_buscada) == 2:
            dia, mes = partes_buscada
            if dia in fecha_texto_lower and mes in fecha_texto_lower:
                return True

        return False

    def _procesar_tabla(self, filas: List, fecha: str) -> List[Partido]:
        """Procesa las filas de una tabla para extraer partidos.

        Cada fila debe tener al menos 4 columnas <td>:
          [Equipos, Liga, Hora, Canal]
        """
        partidos = []

        for fila in filas:
            columnas = fila.find_all("td")
            if len(columnas) >= 4:
                try:
                    equipos = columnas[0].get_text(strip=True)
                    liga = columnas[1].get_text(strip=True)
                    hora = columnas[2].get_text(strip=True)
                    canal = columnas[3].get_text(strip=True)

                    # Validar que todos los campos tengan contenido
                    if all([equipos, liga, hora, canal]) and len(equipos) > 3:
                        partido = Partido(equipos, liga, hora, canal, fecha)
                        partidos.append(partido)
                        logger.debug(f"Partido agregado: {equipos}")

                except Exception as e:
                    logger.warning(f"Error procesando fila: {e}")
                    continue

        return partidos

    def obtener_partidos_hoy(self) -> List[Partido]:
        """Obtiene partidos de hoy"""
        fecha_hoy = self.date_utils.get_hoy()
        return self.obtener_partidos_fecha(fecha_hoy)

    def obtener_partidos_manana(self) -> List[Partido]:
        """Obtiene partidos de mañana"""
        fecha_manana = self.date_utils.get_manana()
        return self.obtener_partidos_fecha(fecha_manana)


class PartidosDeHoyScrapper:
    """Scraper para partidos-de-hoy.co

    Sitio WordPress que muestra partidos organizados por tabs de fecha.
    Cada partido tiene:
      <a class="scf-match-item">
        <div class="scf-match-when">10 Jul 2026, 14:00</div>
        <div class="team-row home"><span class="team-name">Spain</span></div>
        <div class="team-row away"><span class="team-name">Belgium</span></div>
        <div class="scf-match-canal"><img alt="DSports"/></div>
        ...

    NOTA: El sitio carga los tabs dinámicamente (JS), por lo que
    generalmente solo se ve el día actual. Los métodos para 'mañana'
    y fechas específicas intentarán parsear el contenido disponible,
    pero pueden devolver listas vacías si la pestaña no está cargada en HTML.
    """

    URL = "https://partidos-de-hoy.co"

    def __init__(self):
        self.date_utils = DateUtils()
        # Requests normal funciona aquí (no tiene protección CDN agresiva)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "es-ES,es;q=0.9",
            }
        )

    def obtener_partidos_hoy(self) -> List[Partido]:
        """Obtiene partidos de hoy desde partidos-de-hoy.co

        Scrapea todas las ligas y partidos visibles en la página.
        Como el sitio carga por JS, esto generalmente devuelve solo
        los partidos del día actual.
        """
        return self._obtener_partidos()

    def obtener_partidos_manana(self) -> List[Partido]:
        """Obtiene partidos de mañana.

        Intenta parsear todos los tabs disponibles y filtrar por
        la fecha de mañana. Si el tab no está cargado en HTML,
        devuelve lista vacía.
        """
        fecha_manana = DateUtils.get_manana()
        return self.obtener_partidos_fecha(fecha_manana)

    def obtener_partidos_fecha(self, fecha_es: str) -> List[Partido]:
        """Obtiene partidos para una fecha específica en español.

        Scrapea todos los partidos visibles y filtra aquellos
        cuya fecha coincida con la buscada.
        """
        partidos = self._obtener_partidos()
        if not partidos:
            return []

        # Si los partidos ya tienen fecha asignada, filtrar
        # O intentar extraer fecha del texto
        fecha_buscada_lower = fecha_es.lower()
        fecha_buscada_dia = (
            fecha_es.split(" de ")[0] if " de " in fecha_es else fecha_es
        )

        filtrados = []
        for p in partidos:
            # Si el partido ya tiene fecha y coincide, incluirlo
            if p.fecha and p.fecha.lower() == fecha_buscada_lower:
                filtrados.append(p)
            # Si no tiene fecha pero el texto del partido coincide
            elif not p.fecha:
                # Intentar parsear fecha del texto del equipo/hora
                fecha_parseada = DateUtils.parse_fecha_partidos_de_hoy(p.hora)
                if fecha_parseada and fecha_parseada.lower() == fecha_buscada_lower:
                    p.fecha = fecha_es
                    filtrados.append(p)

        return filtrados

    def _obtener_partidos(self) -> List[Partido]:
        """Método interno que scrapea todos los partidos visibles en la página.

        Busca:
        - .scf-league-group:    Agrupaciones por liga
        - .scf-match-item:      Cada partido individual
        - .team-name:           Nombres de equipos
        - .scf-match-canal img: Canal en atributo 'alt'
        """
        try:
            response = self.session.get(self.URL, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            partidos = []

            # Detectar la fecha activa en los tabs (si existe)
            tab_activo = soup.select_one('.scf-tab[aria-selected="true"]')
            fecha_tab = tab_activo.get_text(strip=True) if tab_activo else None
            fecha_es_tab = (
                DateUtils.parse_fecha_partidos_de_hoy(fecha_tab) if fecha_tab else None
            )

            league_groups = soup.select(".scf-league-group")

            for league in league_groups:
                liga = league.find("h2")
                liga_nombre = liga.get_text(strip=True) if liga else "Fútbol"

                match_links = league.select(".scf-match-list li a.scf-match-item")

                for match in match_links:
                    texto = match.get_text(" ", strip=True)

                    if "VS" not in texto:
                        continue

                    # Hora
                    hora = "Por confirmar"
                    for token in texto.split():
                        if ":" in token:
                            hora = token
                            break

                    # Equipos
                    home_team_el = match.select_one(".team-row.home .team-name")
                    away_team_el = match.select_one(".team-row.away .team-name")

                    home_team = (
                        home_team_el.get_text(strip=True)
                        if home_team_el
                        else "Por confirmar"
                    )
                    away_team = (
                        away_team_el.get_text(strip=True)
                        if away_team_el
                        else "Por confirmar"
                    )

                    equipos = f"{home_team} VS {away_team}"

                    # Canal (imagen alt)
                    canal_img = match.select_one(".scf-match-canal img")
                    canal = (
                        canal_img["alt"]
                        if canal_img and canal_img.has_attr("alt")
                        else "Por confirmar"
                    )

                    partidos.append(
                        Partido(
                            equipos=equipos,
                            liga=liga_nombre,
                            hora=hora,
                            canal=canal,
                            fecha=fecha_es_tab,  # Asignar fecha del tab si existe
                        )
                    )

            return partidos

        except requests.RequestException as e:
            logger.error(f"Error de conexión con partidos-de-hoy.co: {e}")
            return []
        except Exception as e:
            logger.error(f"Error inesperado en PartidosDeHoyScrapper: {e}")
            return []


class DataFormatter:
    """Formateador de datos para mensajes del bot.

    Convierte listas de Partido en strings formateados en Markdown
    listos para enviar por Telegram.
    """

    @staticmethod
    def format_partidos(
        partidos: List[Partido], fecha: str, titulo_personalizado: str = None
    ) -> str:
        """Formatea lista de partidos para envío por Telegram con el estilo visual mejorado"""
        if titulo_personalizado:
            encabezado = titulo_personalizado
        else:
            encabezado = f"📅 *Partidos del {fecha}*"

        if not partidos:
            return f"{encabezado}\n\n❌ No se encontraron partidos para esta fecha.\n\n🔄 _Actualizado: {datetime.now().strftime('%H:%M')}h_"

        mensaje = f"{encabezado}\n\n"

        # Formatear cada partido con el nuevo estilo
        for partido in partidos:
            mensaje += partido.to_markdown() + "\n"

        # Agregar total al final
        mensaje += f"📊 Total: {len(partidos)} partidos encontrados"

        return mensaje

    @staticmethod
    def format_resumen_semanal(partidos_por_fecha: Dict[str, List[Partido]]) -> str:
        """Formatea resumen semanal de partidos con el estilo visual mejorado"""
        if not partidos_por_fecha:
            return "📅 *Partidos de la Semana*\n\n❌ No se encontraron partidos para esta semana."

        mensaje = "📅 *Partidos de la Semana*\n\n"

        # Nombres de días en español
        nombres_dias = {
            0: "Hoy",
            1: "Mañana",
            2: "Pasado mañana",
            3: "Miércoles",
            4: "Jueves",
            5: "Viernes",
            6: "Sábado",
        }

        for i, (fecha, partidos) in enumerate(partidos_por_fecha.items()):
            if partidos:
                # Usar nombre del día si está disponible, sino usar la fecha
                nombre_dia = nombres_dias.get(i, fecha)
                mensaje += f"📆 *{nombre_dia}*\n"

                # Agregar todos los partidos de este día con el formato completo
                for partido in partidos:
                    mensaje += partido.to_markdown() + "\n"

                # Agregar total de partidos del día
                mensaje += f"📊 Total: {len(partidos)} partidos encontrados\n\n"

        return mensaje.rstrip()  # Quitar salto de línea final extra


# === FACTORY DE SCRAPERS ===


def get_scraper(source: str = None):
    """Factory: retorna una instancia del scraper según la fuente indicada.

    Orden de precedencia para determinar la fuente:
    1. Parámetro explícito `source`
    2. Variable de entorno SCRAPER_SOURCE (definida en config/.env)
    3. Default: 'partidos-de-hoy'

    Fuentes disponibles:
    - 'futbolred'      : Scraper de futbolred.com (usa curl_cffi para Akamai)
    - 'partidos-de-hoy': Scraper de partidos-de-hoy.co (más estable)

    Uso:
        scraper = get_scraper('futbolred')
        partidos_hoy = scraper.obtener_partidos_hoy()
    """
    if source is None:
        source = os.getenv("SCRAPER_SOURCE", DEFAULT_SOURCE)

    source = source.lower().replace(
        "-", "_"
    )  # Normalizar: 'partidos-de-hoy' -> 'partidos_de_hoy'

    if source == "futbolred":
        logger.info("Usando scraper: futbolred.com (curl_cffi para Akamai)")
        return FutbolRedScraper()

    elif source in ("partidos_de_hoy", "partidos-de-hoy"):
        logger.info("Usando scraper: partidos-de-hoy.co")
        return PartidosDeHoyScrapper()

    else:
        logger.error(f"Fuente no válida: '{source}'. Opciones: {SCRAPER_SOURCES}")
        raise ValueError(
            f"Fuente no válida: '{source}'. Opciones: {', '.join(SCRAPER_SOURCES)}"
        )


# === FUNCIONES PRINCIPALES ===


def obtener_partidos(tipo: str = "hoy", source: str = None) -> str:
    """
    Función principal para obtener partidos formateados.

    Args:
        tipo: 'hoy', 'manana', 'semana'
        source: Fuente de datos (None = usar default/env)

    Returns:
        str: Mensaje formateado en Markdown para Telegram

    La fuente se determina mediante get_scraper():
    - Parámetro source
    - Variable de entorno SCRAPER_SOURCE
    - Default: 'partidos-de-hoy'
    """
    formatter = DataFormatter()

    try:
        # Obtener el scraper según la fuente seleccionada
        scraper = get_scraper(source)

    except ValueError as e:
        logger.error(f"Error de configuración de scraper: {e}")
        return f"❌ *Error de configuración*\n\n{str(e)}"

    try:
        if tipo == "hoy":
            partidos = scraper.obtener_partidos_hoy()
            fecha = DateUtils.get_hoy()
            titulo = f"📺 *Partidos de Hoy ({fecha})*"
            return formatter.format_partidos(partidos, fecha, titulo)

        elif tipo == "manana":
            fecha = DateUtils.get_manana()
            partidos = scraper.obtener_partidos_manana()
            titulo = f"📺 *Partidos de Mañana ({fecha})*"
            return formatter.format_partidos(partidos, fecha, titulo)

        elif tipo == "semana":
            partidos_semana = {}
            for i in range(7):
                fecha_obj = datetime.now() + timedelta(days=i)
                fecha_str = DateUtils.get_fecha_es(fecha_obj)
                partidos = scraper.obtener_partidos_fecha(fecha_str)
                if partidos:
                    partidos_semana[fecha_str] = partidos

            return formatter.format_resumen_semanal(partidos_semana)

        else:
            return "❌ Tipo de consulta no válido. Usa: 'hoy', 'manana' o 'semana'"

    except Exception as e:
        logger.error(f"Error en obtener_partidos: {e}")
        return f"❌ *Error obteniendo partidos*\n\nOcurrió un error al consultar los partidos. Intenta nuevamente en unos minutos.\n\n_Error: {str(e)[:100]}_"


async def enviar_mensaje(tipo: str = "hoy", chat_id: str = None, source: str = None):
    """
    Envía mensaje por Telegram.

    Args:
        tipo: 'hoy', 'manana', 'semana'
        chat_id: ID del chat (opcional, usa CHAT_ID por defecto)
        source: Fuente de datos para get_scraper()
    """
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN no está configurado")
        return False

    if not chat_id:
        chat_id = CHAT_ID

    if not chat_id:
        logger.error("CHAT_ID no está configurado")
        return False

    try:
        logger.info(f"Iniciando envío de partidos ({tipo}) a chat {chat_id}")

        bot = Bot(token=BOT_TOKEN)
        texto = obtener_partidos(tipo, source=source)

        # Verificar longitud del mensaje (Telegram tiene límite de 4096 caracteres)
        if len(texto) > 4000:
            # Dividir mensaje si es muy largo
            partes = [texto[i : i + 4000] for i in range(0, len(texto), 4000)]
            for i, parte in enumerate(partes):
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"{parte}\n\n📄 _Parte {i + 1}/{len(partes)}_",
                    parse_mode="Markdown",
                )
                if i < len(partes) - 1:  # Pausa entre mensajes
                    await asyncio.sleep(1)
        else:
            await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")

        logger.info("Mensaje enviado exitosamente")
        return True

    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        return False


async def enviar_multiple(tipos: List[str] = None, source: str = None):
    """Envía múltiples tipos de partidos"""
    if tipos is None:
        tipos = ["hoy"]

    for tipo in tipos:
        logger.info(f"Enviando partidos: {tipo}")
        await enviar_mensaje(tipo, source=source)
        await asyncio.sleep(2)  # Pausa entre envíos


# === FUNCIÓN PARA PRUEBAS ===


def mostrar_partidos_consola(tipo: str = "hoy", source: str = None):
    """Muestra partidos en consola para pruebas.

    Args:
        tipo: 'hoy', 'manana', 'semana'
        source: Fuente de datos ('futbolred' | 'partidos-de-hoy')
    """
    # Mostrar qué fuente se está usando
    fuente_actual = source or os.getenv("SCRAPER_SOURCE", DEFAULT_SOURCE)
    print(f"\n{'=' * 50}")
    print(f"PROBANDO OBTENCIÓN DE PARTIDOS ({tipo.upper()})")
    print(f"Fuente: {fuente_actual}")
    print(f"{'=' * 50}")

    texto = obtener_partidos(tipo, source=source)
    print(texto)

    print(f"\n{'=' * 50}")
    print(f"PRUEBA COMPLETADA")
    print(f"{'=' * 50}\n")


def parse_cli_args():
    """Parsea argumentos de línea de comandos.

    Soporta:
      python bot_parrilla.py test [tipo] [--source fuente]
      python bot_parrilla.py hoy|manana|semana|todo [--source fuente]

    El argumento --source puede aparecer en cualquier posición.
    """
    args = sys.argv[1:]  # Omitir el nombre del script
    source = None

    # Extraer --source si existe (puede estar en cualquier posición)
    if "--source" in args:
        idx = args.index("--source")
        if idx + 1 < len(args):
            source = args[idx + 1]
            # Remover --source y su valor de args
            args.pop(idx + 1)
            args.pop(idx)

    comando = args[0].lower() if args else None
    tipo = args[1].lower() if len(args) > 1 else "hoy"

    return comando, tipo, source


# === PUNTO DE ENTRADA PRINCIPAL ===
if __name__ == "__main__":
    import sys

    comando, tipo_test, source_cli = parse_cli_args()

    if comando == "test":
        # Modo prueba - mostrar en consola
        mostrar_partidos_consola(tipo_test, source=source_cli)

    elif comando in ("hoy", "manana", "semana", "todo"):
        if comando == "todo":
            asyncio.run(enviar_multiple(["hoy", "manana"], source=source_cli))
        else:
            asyncio.run(enviar_mensaje(comando, source=source_cli))

    elif comando is None:
        # Comportamiento por defecto - enviar partidos de hoy
        logger.info("Ejecutando modo por defecto: partidos de hoy")
        asyncio.run(enviar_mensaje("hoy"))

    else:
        print("❌ Comando no reconocido")
        print("Comandos disponibles:")
        print("  python bot_parrilla.py hoy [--source futbolred|partidos-de-hoy]")
        print("  python bot_parrilla.py manana [--source ...]")
        print("  python bot_parrilla.py semana [--source ...]")
        print("  python bot_parrilla.py todo [--source ...]")
        print("  python bot_parrilla.py test [hoy|manana|semana] [--source ...]")
