import requests
from bs4 import BeautifulSoup
from telegram import Bot
import asyncio
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging
from typing import List, Dict, Optional

# Cargar variables de entorno desde un archivo .env
load_dotenv('config/.env')

# === CONFIGURACIÓN ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL = 'https://www.futbolred.com/parrilla-de-futbol'


# Configurar logging de manera más robusta
def setup_logging():
    """Configura el sistema de logging"""
    # Crear directorio de logs si no existe
    log_dir = 'logs'
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Configurar handlers
        handlers = [logging.StreamHandler()]  # Siempre consola
        
        # Intentar agregar archivo si es posible
        try:
            file_handler = logging.FileHandler('logs/bot_parrilla.log', encoding='utf-8')
            handlers.append(file_handler)
        except Exception as e:
            print(f"⚠️ No se pudo crear archivo de log: {e}")
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        
    except Exception as e:
        # Si todo falla, usar solo consola
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        print(f"⚠️ Configuración de logging simplificada: {e}")


# Inicializar logging
setup_logging()
logger = logging.getLogger('ParrillaCronBot')

# === CLASES Y UTILIDADES MEJORADAS ===

class DateUtils:
    """Utilidades para manejo de fechas"""
    
    MESES_ES: Dict[str, str] = {
        'January': 'enero', 'February': 'febrero', 'March': 'marzo',
        'April': 'abril', 'May': 'mayo', 'June': 'junio',
        'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
        'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
    }
    
    @classmethod
    def get_fecha_es(cls, fecha: datetime = None) -> str:
        """Obtiene la fecha en formato español"""
        if fecha is None:
            fecha = datetime.now()
        
        dia = str(fecha.day)
        mes = cls.MESES_ES[fecha.strftime('%B')]
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

class Partido:
    """Modelo de datos para un partido"""
    
    def __init__(self, equipos: str, liga: str, hora: str, canal: str, fecha: Optional[str] = None):
        self.equipos = equipos
        self.liga = liga
        self.hora = hora
        self.canal = canal
        self.fecha = fecha
        self.emoji_liga = self._get_emoji_liga(liga)
    
    def _get_emoji_liga(self, liga: str) -> str:
        """Obtiene emoji según la liga"""
        liga_lower = liga.lower()
        emoji_map = {
            'liga betplay': '🇨🇴',
            'premier league': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
            'la liga': '🇪🇸',
            'serie a': '🇮🇹',
            'bundesliga': '🇩🇪',
            'ligue 1': '🇫🇷',
            'champions league': '🏆',
            'uefa champions league': '🏆',
            'europa league': '🥈',
            'uefa europa league': '🥈',
            'libertadores': '🏆',
            'copa libertadores': '🏆',
            'sudamericana': '🥉',
            'copa sudamericana': '🥉',
            'eliminatorias': '🌎',
            'mundial': '🌍',
            'copa america': '🏆',
            'eurocopa': '🏆',
        }
        
        for key, emoji in emoji_map.items():
            if key in liga_lower:
                return emoji
        
        return '⚽'
    
    def to_markdown(self) -> str:
        """Convierte el partido a formato markdown con el estilo visual mejorado"""
        return f"{self.emoji_liga} *{self.equipos}*\n   🏆 {self.liga}\n   🕐 {self.hora}\n   📺 {self.canal}\n"

class FutbolRedScraper:
    """Scraper mejorado para FutbolRed"""
    
    def __init__(self):
        self.url = URL
        self.date_utils = DateUtils()
    
    def obtener_partidos_fecha(self, fecha_es: str) -> List[Partido]:
        """Obtiene partidos para una fecha específica"""
        try:
            logger.info(f"🔍 Obteniendo partidos para: {fecha_es}")
            
            # Realizar request con timeout y headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.url, timeout=15, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            tablas = soup.find_all('table')
            partidos = []
            
            logger.info(f"📊 Encontradas {len(tablas)} tablas en la página")
            
            for i, tabla in enumerate(tablas):
                filas = tabla.find_all('tr')
                if not filas:
                    continue
                
                # Verificar si la tabla corresponde a la fecha buscada
                primera_fila = filas[0]
                fecha_texto = primera_fila.get_text(strip=True).lower()
                
                logger.debug(f"Tabla {i+1}: {fecha_texto[:50]}...")
                
                # Verificación más flexible de fecha
                if self._fecha_coincide(fecha_es, fecha_texto):
                    logger.info(f"✅ Fecha encontrada en tabla {i+1}: {fecha_texto}")
                    
                    # Procesar partidos de esta tabla
                    partidos_tabla = self._procesar_tabla(filas[1:], fecha_es)
                    partidos.extend(partidos_tabla)
                    
                    logger.info(f"⚽ Encontrados {len(partidos_tabla)} partidos en esta tabla")
            
            logger.info(f"🎯 Total de partidos encontrados para {fecha_es}: {len(partidos)}")
            return partidos
            
        except requests.RequestException as e:
            logger.error(f"❌ Error de conexión: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Error inesperado obteniendo partidos: {e}")
            return []
    
    def _fecha_coincide(self, fecha_buscada: str, fecha_texto: str) -> bool:
        """Verifica si las fechas coinciden con mayor flexibilidad"""
        fecha_buscada_lower = fecha_buscada.lower()
        fecha_texto_lower = fecha_texto.lower()
        
        # Verificación directa
        if fecha_buscada_lower in fecha_texto_lower:
            return True
        
        # Verificación por partes (día y mes)
        partes_buscada = fecha_buscada_lower.split(' de ')
        if len(partes_buscada) == 2:
            dia, mes = partes_buscada
            if dia in fecha_texto_lower and mes in fecha_texto_lower:
                return True
        
        return False
    
    def _procesar_tabla(self, filas: List, fecha: str) -> List[Partido]:
        """Procesa las filas de una tabla para extraer partidos"""
        partidos = []
        
        for fila in filas:
            columnas = fila.find_all('td')
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
                        logger.debug(f"✅ Partido agregado: {equipos}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando fila: {e}")
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
    URL = "https://partidos-de-hoy.co"
    
    def obtener_partidos_hoy(self) -> List[Partido]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        
        response = requests.get(self.URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        partidos = []
        
        league_groups = soup.select(".scf-league-group")
        
        # 👇 ESTE SELECTOR PUEDE AJUSTARSE
        # cards = soup.select(".match")
        
        # for card in cards:
        #     equipos = card.select_one(".teams")
        #     hora = card.select_one(".time")
        #     liga = card.select_one(".league")
        #     canal = card.select_one(".channel")
            
        #     if not equipos or not hora:
        #         continue
            
        #     partidos.append(
        #         Partido(
        #             equipos=equipos.get_text(strip=True),
        #             liga=liga.get_text(strip=True) if liga else "Fútbol",
        #             hora=hora.get_text(strip=True),
        #             canal=canal.get_text(strip=True) if canal else "Por confirmar"
        #     )
        # )
        
        # return partidos
        
        for league in league_groups:
            liga = league.find("h2")
            liga_nombre = liga.get_text(strip=True) if liga else "Fútbol"

            match_links = league.select(".scf-match-list li a.scf-match-item")

            for match in match_links:
                texto = match.get_text(" ", strip=True)

                # Ejemplo texto:
                # "No iniciado 5 Feb 2026, 20:00 Millonarios VS Deportivo Pereira"

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

                home_team = home_team_el.get_text(strip=True) if home_team_el else "Por confirmar"
                away_team = away_team_el.get_text(strip=True) if away_team_el else "Por confirmar"

                equipos = f"{home_team} VS {away_team}"

                # Canal (imagen alt)
                canal_img = match.select_one(".scf-match-canal img")
                canal = canal_img["alt"] if canal_img and canal_img.has_attr("alt") else "Por confirmar"


                partidos.append(
                    Partido(
                        equipos=equipos,
                        liga=liga_nombre,
                        hora=hora,
                        canal=canal
                    )
                )

        return partidos

class DataFormatter:
    """Formateador de datos para mensajes del bot"""
    
    @staticmethod
    def format_partidos(partidos: List[Partido], fecha: str, titulo_personalizado: str = None) -> str:
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
            6: "Sábado"
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
                mensaje += f"� Total: {len(partidos)} partidos encontrados\n\n"
        
        return mensaje.rstrip() # Quitar salto de línea final extra




# === FUNCIONES PRINCIPALES ===

def obtener_partidos(tipo: str = "hoy") -> str:
    """
    Función principal para obtener partidos
    tipo: 'hoy', 'manana', 'semana'
    """
    formatter = DataFormatter()

    # scraper = FutbolRedScraper()
    
    try:
        if tipo == "hoy":
            scraper = PartidosDeHoyScrapper()
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
        logger.error(f"❌ Error en obtener_partidos: {e}")
        return f"❌ *Error obteniendo partidos*\n\nOcurrió un error al consultar los partidos. Intenta nuevamente en unos minutos.\n\n_Error: {str(e)[:100]}_"

async def enviar_mensaje(tipo: str = "hoy", chat_id: str = None):
    """
    Envía mensaje por Telegram
    tipo: 'hoy', 'manana', 'semana'
    chat_id: ID del chat (opcional, usa CHAT_ID por defecto)
    """
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN no está configurado")
        return False
    
    if not chat_id:
        chat_id = CHAT_ID
    
    if not chat_id:
        logger.error("❌ CHAT_ID no está configurado")
        return False
    
    try:
        logger.info(f"🚀 Iniciando envío de partidos ({tipo}) a chat {chat_id}")
        
        bot = Bot(token=BOT_TOKEN)
        texto = obtener_partidos(tipo)
        
        # Verificar longitud del mensaje (Telegram tiene límite de 4096 caracteres)
        if len(texto) > 4000:
            # Dividir mensaje si es muy largo
            partes = [texto[i:i+4000] for i in range(0, len(texto), 4000)]
            for i, parte in enumerate(partes):
                await bot.send_message(
                    chat_id=chat_id, 
                    text=f"{parte}\n\n📄 _Parte {i+1}/{len(partes)}_", 
                    parse_mode='Markdown'
                )
                if i < len(partes) - 1:  # Pausa entre mensajes
                    await asyncio.sleep(1)
        else:
            await bot.send_message(
                chat_id=chat_id, 
                text=texto, 
                parse_mode='Markdown'
            )
        
        logger.info(f"✅ Mensaje enviado exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error enviando mensaje: {e}")
        return False

async def enviar_multiple(tipos: List[str] = None):
    """Envía múltiples tipos de partidos"""
    if tipos is None:
        tipos = ["hoy"]
    
    for tipo in tipos:
        logger.info(f"📤 Enviando partidos: {tipo}")
        await enviar_mensaje(tipo)
        await asyncio.sleep(2)  # Pausa entre envíos

# === FUNCIÓN PARA PRUEBAS ===
def mostrar_partidos_consola(tipo: str = "hoy"):
    """Muestra partidos en consola para pruebas"""
    print(f"\n{'='*50}")
    print(f"🔍 PROBANDO OBTENCIÓN DE PARTIDOS ({tipo.upper()})")
    print(f"{'='*50}")
    
    texto = obtener_partidos(tipo)
    print(texto)
    
    print(f"\n{'='*50}")
    print(f"✅ PRUEBA COMPLETADA")
    print(f"{'='*50}\n")

# === PUNTO DE ENTRADA PRINCIPAL ===
if __name__ == '__main__':
    import sys
    
    # Configurar argumentos de línea de comandos
    if len(sys.argv) > 1:
        comando = sys.argv[1].lower()
        
        if comando == "test":
            # Modo prueba - mostrar en consola
            tipo_test = sys.argv[2] if len(sys.argv) > 2 else "hoy"
            mostrar_partidos_consola(tipo_test)
            
        elif comando == "hoy":
            asyncio.run(enviar_mensaje("hoy"))
            
        elif comando == "manana":
            asyncio.run(enviar_mensaje("manana"))
            
        elif comando == "semana":
            asyncio.run(enviar_mensaje("semana"))
            
        elif comando == "todo":
            asyncio.run(enviar_multiple(["hoy", "manana"]))
            
        else:
            print("❌ Comando no reconocido")
            print("Comandos disponibles:")
            print("  python bot_parrilla.py hoy")
            print("  python bot_parrilla.py manana")
            print("  python bot_parrilla.py semana")
            print("  python bot_parrilla.py todo")
            print("  python bot_parrilla.py test [hoy|manana|semana]")
    else:
        # Comportamiento por defecto - enviar partidos de hoy
        logger.info("🚀 Ejecutando modo por defecto: partidos de hoy")
        asyncio.run(enviar_mensaje("hoy"))