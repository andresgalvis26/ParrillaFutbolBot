from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv('config/.env')


# Inicializar aplication de Flask
app = Flask(__name__)


# Definir zona horaria de Colombia
TIMEZONE_COL = pytz.timezone('America/Bogota')


# Traer variables de entorno
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN no está definido en las variables de entorno.")
CHAT_ID = os.getenv('CHAT_ID')
if not CHAT_ID:
    raise ValueError("CHAT_ID no está definido en las variables de entorno.")
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
# Para desarrollo local, WEBHOOK_URL es opcional
if not WEBHOOK_URL:
    print("⚠️ WEBHOOK_URL no definido - usando modo de desarrollo local")
    WEBHOOK_URL = "http://localhost:10000"


# Diccionario manual de meses en español
MESES_ES = {
    'January': 'enero', 'February': 'febrero', 'March': 'marzo',
    'April': 'abril', 'May': 'mayo', 'June': 'junio',
    'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
    'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
}

def obtener_partidos():
    # Usar hora de Colombia
    hoy = datetime.now(TIMEZONE_COL)
    dia = str(hoy.day)
    mes = MESES_ES[hoy.strftime('%B')]
    fecha_hoy = f"{dia} de {mes}"
    
    url = 'https://www.futbolred.com/parrilla-de-futbol'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    mensaje = f"📺 *Partidos de hoy ({fecha_hoy}):*\n\n"
    
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
        if f"{dia} de {mes}" in fecha_texto or fecha_hoy in fecha_texto:
            # Procesar las filas de partidos (saltar la primera que es la fecha)
            for fila in filas[1:]:
                columnas = fila.find_all('td')
                if len(columnas) >= 4:
                    partido = columnas[0].get_text(strip=True)
                    liga = columnas[1].get_text(strip=True)
                    hora = columnas[2].get_text(strip=True)
                    canal = columnas[3].get_text(strip=True)
                    
                    if partido and liga and hora and canal:
                        mensaje += f"• {partido} ({liga}) - {hora} por {canal}\n"
                        partidos_encontrados = True
    
    if not partidos_encontrados:
        mensaje += "No se encontraron partidos para hoy."
    
    return mensaje


# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! 👋\n"
        "Soy tu bot de partidos de fútbol.\n\n"
        "Comandos disponibles:\n"
        "/partidos - Ver partidos de hoy\n"
        "/revisar - Ver partidos de hoy\n"
        "/help - Mostrar esta ayuda"
    )

# Comando /partidos (alias de /revisar)
async def partidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    partidos_texto = obtener_partidos()
    await update.message.reply_text(partidos_texto, parse_mode='Markdown')

# Manejar el comando /revisar
async def revisar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    partidos_texto = obtener_partidos()
    await update.message.reply_text(partidos_texto, parse_mode='Markdown')

# Comando /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos disponibles:\n"
        "/start - Mensaje de bienvenida\n"
        "/partidos - Ver partidos de hoy\n"
        "/revisar - Ver partidos de hoy\n"
        "/help - Mostrar esta ayuda"
    )
    
# Ruta de salud para verificar que el servidor funciona
@app.route('/', methods=['GET'])
def health_check():
    return {"status": "Bot funcionando", "commands": ["/start", "/partidos", "/revisar", "/help"]}, 200
    
# Configurar el webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(app_telegram.process_update(update))
    return "ok", 200


# Inicializar la aplicación de Telegram
bot = Bot(token=BOT_TOKEN)
app_telegram = Application.builder().token(BOT_TOKEN).build()

# Registrar comandos
app_telegram.add_handler(CommandHandler("start", start))
app_telegram.add_handler(CommandHandler("partidos", partidos))
app_telegram.add_handler(CommandHandler("revisar", revisar))
app_telegram.add_handler(CommandHandler("help", help_command))

# Establecer webhook al iniciar (solo si no es localhost)
def init_webhook():
    if "localhost" not in WEBHOOK_URL:
        try:
            bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
            print(f"✅ Webhook configurado: {WEBHOOK_URL}/webhook")
        except Exception as e:
            print(f"❌ Error configurando webhook: {e}")
    else:
        print("🔧 Modo desarrollo - sin webhook")

if __name__ == "__main__":
    print("🚀 Iniciando bot...")
    print(f"📡 Webhook URL: {WEBHOOK_URL}")
    
    # Configurar webhook si es necesario
    init_webhook()
    
    print("🌐 Servidor Flask iniciado en puerto 10000")
    print("💬 Bot listo para recibir comandos")
    app.run(host="0.0.0.0", port=10000, debug=True)
