"""
Bot de Telegram para partidos de fútbol (modo interactivo).

Este archivo implementa un bot de Telegram completo con:
  - Comandos: /start, /hoy, /manana, /semana, /status, /help
  - Botones interactivos inline
  - Búsqueda por texto

La obtención de partidos delega en bot_parrilla.py que soporta:
  - Fuente 'futbolred':       FutbolRed.com (curl_cffi para Akamai)
  - Fuente 'partidos-de-hoy': Partidos-de-hoy.co (más estable)

La fuente se selecciona via SCRAPER_SOURCE en config/.env
"""

import os
from dotenv import load_dotenv
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from datetime import datetime, timedelta
import logging

# Importar lógica de scrapping desde bot_parrilla.py
# Esto centraliza toda la lógica de obtención de datos y evita duplicación.
from bot_parrilla import (
    get_scraper,
    DateUtils,
    Partido,
    DataFormatter,
    setup_logging,
    logger as parrilla_logger
)

# Configurar logging (reusa la misma config de bot_parrilla)
setup_logging()
logger = logging.getLogger('ParrillaBot')

# Cargar variables de entorno
load_dotenv('config/.env')

# Traer variables de entorno
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN no está definido en las variables de entorno.")


def obtener_partidos(fecha_objetivo=None, source: str = None) -> str:
    """
    Obtiene los partidos de fútbol de una fecha específica.

    Args:
        fecha_objetivo: datetime object. Si es None, usa la fecha actual.
        source: Fuente de datos ('futbolred' | 'partidos-de-hoy' | None = default/env)

    Returns:
        str: Mensaje formateado con los partidos en Markdown para Telegram.
    """
    if fecha_objetivo is None:
        fecha_objetivo = datetime.now()

    dia = str(fecha_objetivo.day)
    mes = DateUtils.MESES_ES[fecha_objetivo.strftime('%B')]
    fecha_str = f"{dia} de {mes}"

    try:
        logger.info(f"Obteniendo partidos para {fecha_str}...")

        # Obtener scraper según la fuente configurada
        scraper = get_scraper(source=source)

        # Obtener partidos para la fecha
        partidos = scraper.obtener_partidos_fecha(fecha_str)

        formatter = DataFormatter()
        return formatter.format_partidos(partidos, fecha_str)

    except Exception as e:
        logger.error(f"Error obteniendo partidos: {e}")
        return f"❌ Error: No se pudieron obtener los partidos.\n\n_Detalle: {str(e)[:100]}_"


# Comando /start con botones interactivos
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📺 Partidos de Hoy", callback_data='partidos_hoy')],
        [InlineKeyboardButton("🗓️ Partidos de Mañana", callback_data='partidos_manana')],
        [InlineKeyboardButton("📅 Partidos de la Semana", callback_data='partidos_semana')],
        [InlineKeyboardButton("ℹ️ Ayuda", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    mensaje = (
        "¡Hola! Soy tu bot de partidos de fútbol.\n\n"
        "¿Qué puedo hacer por ti?\n\n"
        "Puedo ayudarte a encontrar:\n"
        "• Partidos de hoy y mañana\n"
        "• Horarios y canales de transmisión\n"
        "• Partidos por liga específica\n\n"
        "Elige una opción:"
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
    fecha_manana = datetime.now() + timedelta(days=1)
    partidos_texto = obtener_partidos(fecha_manana)
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
        if "No se encontraron partidos" not in partidos_dia and "Error" not in partidos_dia:
            mensaje_completo += f"📆 *{dia_nombre.capitalize()}*\n"
            # Extraer solo los partidos, sin el encabezado
            partidos_solo = partidos_dia.split('\n\n', 1)[1] if '\n\n' in partidos_dia else partidos_dia
            mensaje_completo += partidos_solo + "\n\n"

    if mensaje_completo == "📅 *Partidos de la Semana:*\n\n":
        mensaje_completo += "No se encontraron partidos para esta semana."

    # Telegram tiene límite de 4096 caracteres
    if len(mensaje_completo) > 4000:
        mensaje_completo = mensaje_completo[:4000] + "\n\n... (lista truncada)"

    await update.message.reply_text(mensaje_completo, parse_mode='Markdown')

# Comando /status - Estado del bot
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from curl_cffi import requests as curl_requests
    try:
        # Probar conexión con futbolred (usa curl_cffi como en el scraper)
        response = curl_requests.get(
            'https://www.futbolred.com/parrilla-de-futbol',
            impersonate='chrome120',
            timeout=10
        )
        status_futbolred = "🟢 OK" if response.status_code == 200 else f"🟡 {response.status_code}"
    except:
        status_futbolred = "🔴 Error de conexión"

    try:
        import requests
        response = requests.get('https://partidos-de-hoy.co', timeout=10)
        status_partidos = "🟢 OK" if response.status_code == 200 else f"🟡 {response.status_code}"
    except:
        status_partidos = "🔴 Error de conexión"

    fuente_actual = os.getenv('SCRAPER_SOURCE', 'partidos-de-hoy')

    mensaje = (
        "📊 *Estado del Bot:*\n\n"
        f"🤖 Bot: 🟢 Funcionando\n"
        f"🌐 FutbolRed: {status_futbolred}\n"
        f"🌐 PartidosDeHoy: {status_partidos}\n"
        f"📋 Fuente activa: `{fuente_actual}`\n"
        f"🕐 Hora: {datetime.now().strftime('%H:%M:%S')}\n"
        f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}\n\n"
        "💡 *Comandos disponibles:*\n"
        "• /hoy - Partidos de hoy\n"
        "• /manana - Partidos de mañana\n"
        "• /semana - Partidos de la semana\n"
        "• /status - Estado del bot\n"
        "• /help - Ayuda completa"
    )

    await update.message.reply_text(mensaje, parse_mode='Markdown')

# Comando /help mejorado
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fuente_actual = os.getenv('SCRAPER_SOURCE', 'partidos-de-hoy')
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
        f"📡 *Fuente de datos:* `{fuente_actual}`\n"
        "• `futbolred`: futbolred.com (via curl_cffi)\n"
        "• `partidos-de-hoy`: partidos-de-hoy.co\n\n"
        "🔍 *Búsqueda por texto:*\n"
        "Puedes escribir palabras como:\n"
        "• `partidos` - Muestra partidos de hoy\n"
        "• `hoy` - Partidos de hoy\n"
        "• `mañana` - Partidos de mañana\n\n"
        "💡 *Consejos:*\n"
        "• Usa los botones del /start para navegación rápida\n"
        "• Para cambiar la fuente, edita SCRAPER_SOURCE en config/.env\n"
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

    elif query.data == 'partidos_manana':
        await query.edit_message_text("🔍 Buscando partidos de mañana...")
        fecha_manana = datetime.now() + timedelta(days=1)
        partidos_texto = obtener_partidos(fecha_manana)
        await query.message.reply_text(partidos_texto, parse_mode='Markdown')

    elif query.data == 'partidos_semana':
        await query.edit_message_text("🔍 Buscando partidos de la semana...")
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
    print("Iniciando bot mejorado en modo local...")
    print("Funcionalidades disponibles:")
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

    print("\nBot iniciado correctamente!")
    print("Comandos disponibles:")
    print("   /start - Menú con botones")
    print("   /hoy - Partidos de hoy")
    print("   /manana - Partidos de mañana")
    print("   /semana - Partidos de la semana")
    print("   /status - Estado del bot")
    print("   /help - Ayuda completa")
    print("\nTambién puedes escribir texto como 'partidos', 'hoy', 'mañana'")
    print("\nPresiona Ctrl+C para detener el bot")

    # Ejecutar el bot
    try:
        application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print("\nBot detenido por el usuario")
    except Exception as e:
        logger.error(f"Error ejecutando el bot: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
