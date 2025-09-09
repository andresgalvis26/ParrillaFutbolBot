import os
from dotenv import load_dotenv
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
import asyncio

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('config/.env')

# Traer variables de entorno
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN no está definido en las variables de entorno.")

# Diccionario manual de meses en español
MESES_ES = {
    'January': 'enero', 'February': 'febrero', 'March': 'marzo',
    'April': 'abril', 'May': 'mayo', 'June': 'junio',
    'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
    'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
}

def obtener_partidos(fecha_objetivo=None):
    """
    Obtiene los partidos de fútbol de una fecha específica
    
    Args:
        fecha_objetivo: datetime object. Si es None, usa la fecha actual
    
    Returns:
        str: Mensaje formateado con los partidos
    """
    if fecha_objetivo is None:
        fecha_objetivo = datetime.now()
    
    dia = str(fecha_objetivo.day)
    mes = MESES_ES[fecha_objetivo.strftime('%B')]
    fecha_str = f"{dia} de {mes}"
    
    url = 'https://www.futbolred.com/parrilla-de-futbol'
    
    try:
        logger.info(f"Obteniendo partidos para {fecha_str}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        mensaje = f"📺 *Partidos del {fecha_str}:*\n\n"
        
        # Buscar todas las tablas en la página
        tablas = soup.find_all('table')
        partidos_encontrados = False
        contador_partidos = 0
        
        for tabla in tablas:
            filas = tabla.find_all('tr')
            if not filas:
                continue
                
            # La primera fila contiene la fecha
            primera_fila = filas[0]
            fecha_texto = primera_fila.get_text(strip=True).lower()
            
            # Verificar si la fecha coincide
            if f"{dia} de {mes}" in fecha_texto or fecha_str.lower() in fecha_texto:
                logger.info(f"Fecha encontrada: {fecha_texto}")
                
                # Procesar las filas de partidos (saltar la primera que es la fecha)
                for fila in filas[1:]:
                    columnas = fila.find_all('td')
                    if len(columnas) >= 4:
                        partido = columnas[0].get_text(strip=True)
                        liga = columnas[1].get_text(strip=True)
                        hora = columnas[2].get_text(strip=True)
                        canal = columnas[3].get_text(strip=True)
                        
                        if partido and liga and hora and canal:
                            contador_partidos += 1
                            # Emojis por tipo de liga
                            emoji = get_liga_emoji(liga)
                            mensaje += f"{emoji} *{partido}*\n"
                            mensaje += f"   🏆 {liga}\n"
                            mensaje += f"   🕐 {hora}\n"
                            mensaje += f"   📺 {canal}\n\n"
                            partidos_encontrados = True
        
        if not partidos_encontrados:
            mensaje += "No se encontraron partidos para esta fecha. 😔\n\n"
            mensaje += "💡 Prueba con:\n"
            mensaje += "• /hoy - Partidos de hoy\n"
            mensaje += "• /mañana - Partidos de mañana\n"
            mensaje += "• /semana - Partidos de la semana"
        else:
            mensaje += f"📊 Total: {contador_partidos} partidos encontrados"
        
        return mensaje
    
    except requests.RequestException as e:
        logger.error(f"Error de conexión: {e}")
        return f"❌ Error de conexión: No se pudo acceder a la página de partidos.\n\nIntenta nuevamente en unos minutos."
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return f"❌ Error inesperado: {str(e)}"

def get_liga_emoji(liga):
    """Retorna emoji apropiado según la liga"""
    liga_lower = liga.lower()
    if 'premier' in liga_lower or 'premier league' in liga_lower:
        return "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
    elif 'champions' in liga_lower or 'uefa' in liga_lower:
        return "🏆"
    elif 'colombia' in liga_lower or 'betplay' in liga_lower:
        return "🇨🇴"
    elif 'argentina' in liga_lower:
        return "🇦🇷"
    elif 'brasil' in liga_lower or 'brazil' in liga_lower:
        return "🇧🇷"
    elif 'españa' in liga_lower or 'laliga' in liga_lower or 'la liga' in liga_lower:
        return "🇪🇸"
    elif 'italia' in liga_lower or 'serie a' in liga_lower:
        return "🇮🇹"
    elif 'francia' in liga_lower or 'ligue' in liga_lower:
        return "🇫🇷"
    elif 'alemania' in liga_lower or 'bundesliga' in liga_lower:
        return "🇩🇪"
    elif 'amistoso' in liga_lower:
        return "🤝"
    else:
        return "⚽"

# Comando /start con botones interactivos
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📺 Partidos de Hoy", callback_data='partidos_hoy')],
        [InlineKeyboardButton("🗓️ Partidos de Mañana", callback_data='partidos_mañana')],
        [InlineKeyboardButton("📅 Partidos de la Semana", callback_data='partidos_semana')],
        [InlineKeyboardButton("ℹ️ Ayuda", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensaje = (
        "¡Hola! 👋 Soy tu bot de partidos de fútbol.\n\n"
        "🎯 *¿Qué puedo hacer por ti?*\n\n"
        "Puedo ayudarte a encontrar:\n"
        "• Partidos de hoy y mañana\n"
        "• Horarios y canales de transmisión\n"
        "• Partidos por liga específica\n\n"
        "🔽 *Elige una opción:*"
    )
    
    await update.message.reply_text(mensaje, parse_mode='Markdown', reply_markup=reply_markup)

# Comando /partidos (hoy)
async def partidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Buscando partidos de hoy...")
    partidos_texto = obtener_partidos()
    await update.message.reply_text(partidos_texto, parse_mode='Markdown')

# Comando /hoy
async def hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Buscando partidos de hoy...")
    partidos_texto = obtener_partidos()
    await update.message.reply_text(partidos_texto, parse_mode='Markdown')

# Comando /manana (sin ñ para compatibilidad)
async def manana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Buscando partidos de mañana...")
    fecha_mañana = datetime.now() + timedelta(days=1)
    partidos_texto = obtener_partidos(fecha_mañana)
    await update.message.reply_text(partidos_texto, parse_mode='Markdown')

# Comando /semana
async def semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Buscando partidos de los próximos 7 días...")
    
    mensaje_completo = "📅 *Partidos de la Semana:*\n\n"
    
    for i in range(7):
        fecha = datetime.now() + timedelta(days=i)
        dia_nombre = ["Hoy", "Mañana", "Pasado mañana"][i] if i < 3 else fecha.strftime("%A")
        
        # Obtener partidos para cada día
        partidos_dia = obtener_partidos(fecha)
        
        # Solo agregar días que tengan partidos
        if "No se encontraron partidos" not in partidos_dia:
            mensaje_completo += f"📆 *{dia_nombre.capitalize()}*\n"
            # Extraer solo los partidos, sin el encabezado
            partidos_solo = partidos_dia.split('\n\n', 1)[1] if '\n\n' in partidos_dia else partidos_dia
            mensaje_completo += partidos_solo + "\n\n"
    
    if mensaje_completo == "📅 *Partidos de la Semana:*\n\n":
        mensaje_completo += "No se encontraron partidos para esta semana. 😔"
    
    # Telegram tiene límite de 4096 caracteres
    if len(mensaje_completo) > 4000:
        mensaje_completo = mensaje_completo[:4000] + "\n\n... (lista truncada)"
    
    await update.message.reply_text(mensaje_completo, parse_mode='Markdown')

# Comando /status - Estado del bot
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Probar conexión
        response = requests.get('https://www.futbolred.com/parrilla-de-futbol', timeout=5)
        status_web = "🟢 Conectado" if response.status_code == 200 else "🟡 Problemas de conexión"
    except:
        status_web = "🔴 Sin conexión"
    
    mensaje = (
        "📊 *Estado del Bot:*\n\n"
        f"🤖 Bot: 🟢 Funcionando\n"
        f"🌐 Web: {status_web}\n"
        f"🕐 Hora: {datetime.now().strftime('%H:%M:%S')}\n"
        f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}\n\n"
        "💡 *Comandos disponibles:*\n"
        "• /hoy - Partidos de hoy\n"
        "• /mañana - Partidos de mañana\n"
        "• /semana - Partidos de la semana\n"
        "• /status - Estado del bot\n"
        "• /help - Ayuda completa"
    )
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')

# Comando /help mejorado
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🆘 *Ayuda - Bot de Partidos de Fútbol*\n\n"
        "📋 *Comandos principales:*\n"
        "• `/start` - Menú principal con botones\n"
        "• `/hoy` - Partidos de hoy\n"
        "• `/manana` - Partidos de mañana\n"
        "• `/partidos` - Alias de /hoy\n"
        "• `/semana` - Partidos de los próximos 7 días\n"
        "• `/status` - Estado del bot y conexión\n"
        "• `/help` - Esta ayuda\n\n"
        "🔍 *Búsqueda por texto:*\n"
        "Puedes escribir palabras como:\n"
        "• `partidos` - Muestra partidos de hoy\n"
        "• `fútbol` - Muestra partidos de hoy\n"
        "• `hoy` - Partidos de hoy\n"
        "• `mañana` - Partidos de mañana\n\n"
        "💡 *Consejos:*\n"
        "• Usa los botones del /start para navegación rápida\n"
        "• El bot se actualiza automáticamente desde futbolred.com\n"
        "• Los partidos incluyen horarios y canales de TV\n\n"
        "❓ *¿Problemas?*\n"
        "Usa /status para verificar la conexión"
    )
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')

# Manejador de botones inline
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'partidos_hoy':
        await query.edit_message_text("🔍 Buscando partidos de hoy...")
        partidos_texto = obtener_partidos()
        await query.message.reply_text(partidos_texto, parse_mode='Markdown')
        
    elif query.data == 'partidos_mañana':
        await query.edit_message_text("🔍 Buscando partidos de mañana...")
        fecha_mañana = datetime.now() + timedelta(days=1)
        partidos_texto = obtener_partidos(fecha_mañana)
        await query.message.reply_text(partidos_texto, parse_mode='Markdown')
        
    elif query.data == 'partidos_semana':
        await query.edit_message_text("🔍 Buscando partidos de la semana...")
        # Llamar a la función semana
        await semana(update, context)
        
    elif query.data == 'help':
        await help_command(update, context)

# Manejador de mensajes de texto
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if any(palabra in text for palabra in ['partidos', 'fútbol', 'futbol', 'hoy']):
        await hoy(update, context)
    elif 'mañana' in text:
        await manana(update, context)
    elif 'semana' in text:
        await semana(update, context)
    elif any(palabra in text for palabra in ['ayuda', 'help', 'comando']):
        await help_command(update, context)
    elif any(palabra in text for palabra in ['estado', 'status', 'funciona']):
        await status(update, context)
    else:
        await update.message.reply_text(
            "🤔 No entiendo ese comando.\n\n"
            "Prueba con:\n"
            "• `/start` - Para ver el menú principal\n"
            "• `/help` - Para ver todos los comandos\n"
            "• Escribe 'partidos' para ver los de hoy"
        )

def main():
    print("🚀 Iniciando bot mejorado en modo local...")
    print("📊 Funcionalidades disponibles:")
    print("   • Partidos de hoy, mañana y semana")
    print("   • Botones interactivos")
    print("   • Búsqueda por texto")
    print("   • Emojis por liga")
    print("   • Estado de conexión")
    
    # Crear la aplicación
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Registrar comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("partidos", partidos))
    application.add_handler(CommandHandler("hoy", hoy))
    application.add_handler(CommandHandler("manana", manana))
    application.add_handler(CommandHandler("semana", semana))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("help", help_command))
    
    # Manejador de botones
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Manejador de texto
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("\n✅ Bot iniciado correctamente!")
    print("🎮 Comandos disponibles:")
    print("   /start - Menú con botones")
    print("   /hoy - Partidos de hoy")
    print("   /manana - Partidos de mañana")
    print("   /semana - Partidos de la semana")
    print("   /status - Estado del bot")
    print("   /help - Ayuda completa")
    print("\n💡 También puedes escribir texto como 'partidos', 'hoy', 'mañana'")
    print("\n🛑 Presiona Ctrl+C para detener el bot")
    
    # Ejecutar el bot
    try:
        application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print("\n👋 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"Error ejecutando el bot: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
