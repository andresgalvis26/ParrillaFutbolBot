"""
Bot de Telegram para partidos de fútbol (modo interactivo).

Este archivo implementa un bot de Telegram completo con:
  - Menú interactivo multi-paso: selección de fuente -> selección de consulta
  - Comandos: /start, /hoy, /manana, /semana, /status, /help, /source
  - Botones inline con flujo guiado
  - La fuente elegida por el usuario se recuerda en memoria por chat

La obtención de partidos delega en bot_parrilla.py que soporta:
  - Fuente 'futbolred':       FutbolRed.com (curl_cffi para Akamai)
  - Fuente 'partidos-de-hoy': Partidos-de-hoy.co (más estable)

La fuente se determina en este orden:
  1. Preferencia del usuario (guardada en memoria)
  2. Variable SCRAPER_SOURCE en config/.env
  3. Default: 'partidos-de-hoy'
"""

import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict

from bot_parrilla import (
    get_scraper,
    DateUtils,
    DataFormatter,
    setup_logging,
)

setup_logging()
logger = logging.getLogger('ParrillaBot')

load_dotenv(os.path.join(os.path.dirname(__file__), 'config', '.env'))

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN no está definido en las variables de entorno.")

# Preferencias de fuente por chat_id (en memoria: se pierde al reiniciar el bot)
# Estructura: {chat_id: 'futbolred' | 'partidos-de-hoy'}
user_sources: Dict[int, str] = {}

COL_TZ = timezone(timedelta(hours=-5))

# Nombres para mostrar
SOURCE_DISPLAY = {
    'futbolred': 'futbolred.com',
    'partidos-de-hoy': 'partidos-de-hoy.co',
    'futbolenvivo': 'futbolenvivocolombia.com',
}
SOURCE_EMOJI = {
    'futbolred': '🌐',
    'partidos-de-hoy': '⚽',
    'futbolenvivo': '📺',
}

# === CALLBACK DATA CONSTANTS ===
CB_SOURCE_FUTBOLRED = 'src_futbolred'
CB_SOURCE_PARTIDOS = 'src_partidos'
CB_SOURCE_FUTBOLENVIVO = 'src_futbolenvivo'
CB_HOY = 'partidos_hoy'
CB_MANANA = 'partidos_manana'
CB_SEMANA = 'partidos_semana'
CB_HELP = 'help'


def obtener_source_usuario(chat_id: int) -> str:
    """Retorna la fuente configurada para un chat, con fallback a env/default."""
    if chat_id in user_sources:
        return user_sources[chat_id]
    return os.getenv('SCRAPER_SOURCE', 'partidos-de-hoy')


def obtener_partidos(fecha_objetivo=None, source: str = None, chat_id: int = None) -> str:
    """
    Obtiene los partidos de fútbol de una fecha específica.

    Args:
        fecha_objetivo: datetime object. Si es None, usa la fecha actual.
        source: Fuente explícita. Si es None, se obtiene del chat_id o env.
        chat_id: ID del chat para recuperar su fuente preferida.

    Returns:
        str: Mensaje formateado con los partidos en Markdown para Telegram.
    """
    if fecha_objetivo is None:
        fecha_objetivo = datetime.now(COL_TZ)

    dia = str(fecha_objetivo.day)
    mes = DateUtils.MESES_ES[fecha_objetivo.strftime('%B')]
    fecha_str = f"{dia} de {mes}"

    # Resolver fuente: parámetro > preferencia usuario > env > default
    if source is None:
        source = obtener_source_usuario(chat_id) if chat_id else os.getenv('SCRAPER_SOURCE', 'partidos-de-hoy')

    try:
        logger.info(f"Obteniendo partidos para {fecha_str} (fuente: {source})...")
        scraper, nombre_fuente = get_scraper(source=source)
        partidos = scraper.obtener_partidos_fecha(fecha_str)
        formatter = DataFormatter()
        return formatter.format_partidos(partidos, fecha_str, fuente=nombre_fuente)

    except Exception as e:
        logger.error(f"Error obteniendo partidos: {e}")
        return f"❌ Error: No se pudieron obtener los partidos.\n\n_Detalle: {str(e)[:100]}_"


def menu_principal(chat_id: int) -> tuple:
    """Retorna (mensaje, markup) del menú principal con la fuente actual."""
    fuente = obtener_source_usuario(chat_id)
    display = SOURCE_DISPLAY.get(fuente, fuente)
    emoji = SOURCE_EMOJI.get(fuente, '📡')

    keyboard = [
        [InlineKeyboardButton("📺 Partidos de Hoy", callback_data=CB_HOY)],
        [InlineKeyboardButton("🗓️ Partidos de Mañana", callback_data=CB_MANANA)],
        [InlineKeyboardButton("📅 Partidos de la Semana", callback_data=CB_SEMANA)],
        [InlineKeyboardButton(f"{emoji} Cambiar Fuente ({display})", callback_data='cambiar_fuente')],
        [InlineKeyboardButton("ℹ️ Ayuda", callback_data=CB_HELP)],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    mensaje = (
        "¡Hola! Soy tu bot de partidos de fútbol.\n\n"
        "¿Qué quieres consultar?\n\n"
        f"{emoji} *Fuente activa:* `{display}`"
    )
    return mensaje, markup


def menu_fuentes(chat_id: int) -> tuple:
    """Retorna (mensaje, markup) del selector de fuentes."""
    actual = obtener_source_usuario(chat_id)

    keyboard = []
    source_keys = [('futbolred', CB_SOURCE_FUTBOLRED), ('partidos-de-hoy', CB_SOURCE_PARTIDOS), ('futbolenvivo', CB_SOURCE_FUTBOLENVIVO)]
    for key, cb in source_keys:
        display = SOURCE_DISPLAY[key]
        emoji = SOURCE_EMOJI[key]
        marca = " ✅" if key == actual else ""
        keyboard.append([InlineKeyboardButton(f"{emoji} {display}{marca}", callback_data=cb)])

    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data='volver_menu')])
    markup = InlineKeyboardMarkup(keyboard)

    mensaje = (
        "📡 *Selecciona tu fuente de datos:*\n\n"
        "• `futbolred`: Datos desde FutbolRed.com\n"
        "• `partidos-de-hoy`: Datos desde Partidos-de-hoy.co\n\n"
        "Elige la que prefieras:"
    )
    return mensaje, markup


# === COMANDOS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start: muestra selector de fuente si es la primera vez, o menú principal."""
    chat_id = update.effective_chat.id

    if chat_id not in user_sources:
        # Primera vez: preguntar fuente primero
        mensaje, markup = menu_fuentes(chat_id)
        await update.message.reply_text(mensaje, parse_mode='Markdown', reply_markup=markup)
    else:
        # Ya tiene fuente: ir directo al menú principal
        mensaje, markup = menu_principal(chat_id)
        await update.message.reply_text(mensaje, parse_mode='Markdown', reply_markup=markup)


async def source_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /source: permite cambiar la fuente manualmente."""
    chat_id = update.effective_chat.id
    mensaje, markup = menu_fuentes(chat_id)
    await update.message.reply_text(mensaje, parse_mode='Markdown', reply_markup=markup)


async def partidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /partidos (hoy)."""
    chat_id = update.effective_chat.id
    await update.message.reply_text("🔍 Buscando partidos de hoy...")
    texto = obtener_partidos(chat_id=chat_id)
    await update.message.reply_text(texto, parse_mode='Markdown')


async def hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /hoy."""
    chat_id = update.effective_chat.id
    await update.message.reply_text("🔍 Buscando partidos de hoy...")
    texto = obtener_partidos(chat_id=chat_id)
    await update.message.reply_text(texto, parse_mode='Markdown')


async def manana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /manana."""
    chat_id = update.effective_chat.id
    await update.message.reply_text("🔍 Buscando partidos de mañana...")
    fecha_manana = datetime.now(COL_TZ) + timedelta(days=1)
    texto = obtener_partidos(fecha_manana, chat_id=chat_id)
    await update.message.reply_text(texto, parse_mode='Markdown')


def generar_mensaje_semana(chat_id: int = None) -> str:
    """Genera el texto del resumen semanal."""
    mensaje_completo = "📅 *Partidos de la Semana:*\n\n"

    for i in range(7):
        fecha = datetime.now(COL_TZ) + timedelta(days=i)
        dia_nombre = ["Hoy", "Mañana", "Pasado mañana"][i] if i < 3 else fecha.strftime("%A")

        partidos_dia = obtener_partidos(fecha, chat_id=chat_id)

        if "No se encontraron partidos" not in partidos_dia and "Error" not in partidos_dia:
            mensaje_completo += f"📆 *{dia_nombre.capitalize()}*\n"
            partidos_solo = partidos_dia.split('\n\n', 1)[1] if '\n\n' in partidos_dia else partidos_dia
            mensaje_completo += partidos_solo + "\n\n"

    if mensaje_completo == "📅 *Partidos de la Semana:*\n\n":
        mensaje_completo += "No se encontraron partidos para esta semana."

    if len(mensaje_completo) > 4000:
        mensaje_completo = mensaje_completo[:4000] + "\n\n... (lista truncada)"

    return mensaje_completo


async def semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /semana."""
    chat_id = update.effective_chat.id
    await update.message.reply_text("🔍 Buscando partidos de los próximos 7 días...")
    mensaje_completo = generar_mensaje_semana(chat_id=chat_id)
    await update.message.reply_text(mensaje_completo, parse_mode='Markdown')


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /status."""
    from curl_cffi import requests as curl_requests
    import requests
    chat_id = update.effective_chat.id
    fuente = obtener_source_usuario(chat_id)
    display = SOURCE_DISPLAY.get(fuente, fuente)

    try:
        r = curl_requests.get('https://www.futbolred.com/parrilla-de-futbol', impersonate='chrome120', timeout=10)
        status_futbolred = "🟢 OK" if r.status_code == 200 else f"🟡 {r.status_code}"
    except:
        status_futbolred = "🔴 Error"

    try:
        r = requests.get('https://partidos-de-hoy.co', timeout=10)
        status_partidos = "🟢 OK" if r.status_code == 200 else f"🟡 {r.status_code}"
    except:
        status_partidos = "🔴 Error"

    mensaje = (
        "📊 *Estado del Bot:*\n\n"
        f"🤖 Bot: 🟢 Funcionando\n"
        f"🌐 FutbolRed: {status_futbolred}\n"
        f"⚽ PartidosDeHoy: {status_partidos}\n"
        f"📋 Tu fuente: `{display}`\n"
        f"🕐 Hora: {datetime.now(COL_TZ).strftime('%H:%M:%S')}\n\n"
        "💡 Usá /start para el menú o /source para cambiar fuente."
    )
    await update.message.reply_text(mensaje, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help."""
    chat_id = update.effective_chat.id
    fuente = obtener_source_usuario(chat_id)
    display = SOURCE_DISPLAY.get(fuente, fuente)

    mensaje = (
        "🆘 *Ayuda - Bot de Partidos de Fútbol*\n\n"
        "📋 *Comandos:*\n"
        "• `/start` - Menú principal\n"
        "• `/hoy` - Partidos de hoy\n"
        "• `/manana` - Partidos de mañana\n"
        "• `/semana` - Partidos de la semana\n"
        "• `/source` - Cambiar fuente de datos\n"
        "• `/status` - Estado del bot\n"
        "• `/help` - Esta ayuda\n\n"
        f"📡 *Tu fuente:* `{display}`\n"
        "Usá /source para cambiarla.\n\n"
        "💡 También escribí `partidos`, `hoy` o `mañana` en el chat."
    )
    await update.message.reply_text(mensaje, parse_mode='Markdown')


# === MANEJADOR DE BOTONES ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los botones inline del bot."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    data = query.data

    # === SELECCIÓN DE FUENTE ===
    if data == CB_SOURCE_FUTBOLRED:
        user_sources[chat_id] = 'futbolred'
        fuente = SOURCE_DISPLAY['futbolred']
        mensaje, markup = menu_principal(chat_id)
        await query.edit_message_text(
            f"✅ *Fuente seleccionada:* {fuente}\n\n{mensaje}",
            parse_mode='Markdown',
            reply_markup=markup,
        )
        return

    if data == CB_SOURCE_PARTIDOS:
        user_sources[chat_id] = 'partidos-de-hoy'
        fuente = SOURCE_DISPLAY['partidos-de-hoy']
        mensaje, markup = menu_principal(chat_id)
        await query.edit_message_text(
            f"✅ *Fuente seleccionada:* {fuente}\n\n{mensaje}",
            parse_mode='Markdown',
            reply_markup=markup,
        )
        return

    if data == CB_SOURCE_FUTBOLENVIVO:
        user_sources[chat_id] = 'futbolenvivo'
        fuente = SOURCE_DISPLAY['futbolenvivo']
        mensaje, markup = menu_principal(chat_id)
        await query.edit_message_text(
            f"✅ *Fuente seleccionada:* {fuente}\n\n{mensaje}",
            parse_mode='Markdown',
            reply_markup=markup,
        )
        return

    if data == 'cambiar_fuente':
        mensaje, markup = menu_fuentes(chat_id)
        await query.edit_message_text(mensaje, parse_mode='Markdown', reply_markup=markup)
        return

    if data == 'volver_menu':
        mensaje, markup = menu_principal(chat_id)
        await query.edit_message_text(mensaje, parse_mode='Markdown', reply_markup=markup)
        return

    # === ACCIONES DEL MENÚ PRINCIPAL ===
    if data == CB_HOY:
        await query.edit_message_text("🔍 Buscando partidos de hoy...")
        texto = obtener_partidos(chat_id=chat_id)
        await query.message.reply_text(texto, parse_mode='Markdown')
        return

    if data == CB_MANANA:
        await query.edit_message_text("🔍 Buscando partidos de mañana...")
        fecha_manana = datetime.now(COL_TZ) + timedelta(days=1)
        texto = obtener_partidos(fecha_manana, chat_id=chat_id)
        await query.message.reply_text(texto, parse_mode='Markdown')
        return

    if data == CB_SEMANA:
        await query.edit_message_text("🔍 Buscando partidos de la semana...")
        mensaje_completo = generar_mensaje_semana(chat_id=chat_id)
        await query.message.reply_text(mensaje_completo, parse_mode='Markdown')
        return

    if data == CB_HELP:
        await help_command(update, context)
        return


# === MANEJADOR DE TEXTO ===

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde a mensajes de texto libre."""
    chat_id = update.effective_chat.id
    text = update.message.text.lower()

    if any(p in text for p in ['partidos', 'fútbol', 'futbol', 'hoy']):
        await update.message.reply_text("🔍 Buscando partidos de hoy...")
        texto = obtener_partidos(chat_id=chat_id)
        await update.message.reply_text(texto, parse_mode='Markdown')
    elif 'mañana' in text:
        await update.message.reply_text("🔍 Buscando partidos de mañana...")
        fecha_manana = datetime.now(COL_TZ) + timedelta(days=1)
        texto = obtener_partidos(fecha_manana, chat_id=chat_id)
        await update.message.reply_text(texto, parse_mode='Markdown')
    elif 'semana' in text:
        await semana(update, context)
    elif any(p in text for p in ['ayuda', 'help', 'comando']):
        await help_command(update, context)
    elif any(p in text for p in ['fuente', 'source', 'cambiar']):
        mensaje, markup = menu_fuentes(chat_id)
        await update.message.reply_text(mensaje, parse_mode='Markdown', reply_markup=markup)
    elif any(p in text for p in ['estado', 'status', 'funciona']):
        await status(update, context)
    else:
        mensaje, markup = menu_principal(chat_id) if chat_id in user_sources else menu_fuentes(chat_id)
        await update.message.reply_text(
            "🤔 No entiendo ese comando.\n\nUsá /start para ver el menú.",
            reply_markup=markup,
        )


# === MAIN ===

def main():
    print("Iniciando bot con menú interactivo multi-paso...")
    print("Características:")
    print("   • Selección de fuente al iniciar")
    print("   • Partidos de hoy, mañana y semana")
    print("   • Botones interactivos")
    print("   • Búsqueda por texto")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("source", source_command))
    application.add_handler(CommandHandler("partidos", partidos))
    application.add_handler(CommandHandler("hoy", hoy))
    application.add_handler(CommandHandler("manana", manana))
    application.add_handler(CommandHandler("semana", semana))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("\nBot iniciado correctamente!")
    print("Comandos: /start, /hoy, /manana, /semana, /source, /status, /help")
    print("\nPresiona Ctrl+C para detener el bot")

    try:
        application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print("\nBot detenido por el usuario")
    except Exception as e:
        logger.error(f"Error ejecutando el bot: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
