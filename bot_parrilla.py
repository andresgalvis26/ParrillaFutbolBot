import requests
from bs4 import BeautifulSoup
from telegram import Bot
import asyncio
from datetime import datetime
import locale


# === CONFIGURA ESTOS VALORES ===
BOT_TOKEN = '8431535855:AAFYG6ljzb5gkoAHY2jHRwKs4RVCIbHRchk'
CHAT_ID = '702417211'
URL = 'https://www.futbolred.com/parrilla-de-futbol'


# === FUNCIÓN PARA OBTENER LOS PARTIDOS DEL DÍA ===
def obtener_partidos():
    
    # Establecer español como idioma para la fecha
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8') # Linux / Mac
    except:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252') # Windows
    
    hoy = datetime.now()
    dia = str(hoy.day)
    mes = hoy.strftime('%B').lower()
    fecha_hoy = f"{dia} de {mes}"
    
    # Realizar scraping
    response = requests.get(URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    mensaje = f"📺 *Partidos de hoy ({fecha_hoy}):*\n\n"
    
    print(f"Buscando partidos para el {fecha_hoy}...")  # Mensaje de depuración
    
    # Buscar todas las tablas en la página
    tablas = soup.find_all('table')
    partidos_encontrados = False
    
    for tabla in tablas:
        filas = tabla.find_all('tr')
        if not filas:
            continue
            
        # La primera fila contiene la fecha
        primera_fila = filas[0]
        fecha_texto = primera_fila.get_text(strip=True).lower()
        
        # Verificar si la fecha coincide con hoy
        if f"{dia} de agosto" in fecha_texto or fecha_hoy in fecha_texto:
            print(f"Fecha encontrada: {fecha_texto}")
            
            # Procesar las filas de partidos (saltar la primera que es la fecha)
            for fila in filas[1:]:
                columnas = fila.find_all('td')
                if len(columnas) >= 4:
                    partido = columnas[0].get_text(strip=True)
                    liga = columnas[1].get_text(strip=True)
                    hora = columnas[2].get_text(strip=True)
                    canal = columnas[3].get_text(strip=True)
                    
                    if partido and liga and hora and canal:  # Verificar que no estén vacías
                        mensaje += f"• {partido} ({liga}) - {hora} por {canal}\n"
                        partidos_encontrados = True
    
    if not partidos_encontrados:
        mensaje += "No se encontraron partidos para hoy."
    
    return mensaje


# === ENVÍA EL MENSAJE POR TELEGRAM ===
async def enviar_mensaje():
    bot = Bot(token=BOT_TOKEN)
    texto = obtener_partidos()
    await bot.send_message(chat_id=CHAT_ID, text=texto, parse_mode='Markdown')


# === PRUEBA MANUAL ===
if __name__ == '__main__':
    asyncio.run(enviar_mensaje())