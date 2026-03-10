import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, CallbackQueryHandler, ContextTypes, filters
)
from flight_search import search_flights, format_flight_message

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados de la conversación
ORIGIN, DESTINATION, DATE_OUT, DATE_IN, PASSENGERS = range(5)

AIRPORTS = {
    'ALC': 'Alicante',
    'RMU': 'Murcia',
    'MAD': 'Madrid',
    'BCN': 'Barcelona',
    'VLC': 'Valencia',
    'PMI': 'Palma de Mallorca',
    'LHR': 'Londres Heathrow',
    'LTN': 'Londres Luton',
    'STN': 'Londres Stansted',
    'CDG': 'París',
    'FCO': 'Roma',
    'AMS': 'Ámsterdam',
    'BER': 'Berlín',
    'MXP': 'Milán',
    'DUB': 'Dublín',
    'LIS': 'Lisboa',
    'VIE': 'Viena',
    'ATH': 'Atenas',
    'PRG': 'Praga',
    'BUD': 'Budapest',
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✈️ *Bot de Vuelos Grupales*\n\n"
        "Te ayudo a encontrar vuelos donde *todo el grupo viaje junto*.\n\n"
        "Usa /buscar para iniciar una búsqueda.\n"
        "Usa /ayuda para ver los comandos disponibles.",
        parse_mode='Markdown'
    )


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Comandos disponibles:*\n\n"
        "/buscar — Iniciar búsqueda de vuelo\n"
        "/cancelar — Cancelar búsqueda actual\n"
        "/ayuda — Mostrar esta ayuda\n\n"
        "El bot busca vuelos con plazas suficientes para todo el grupo "
        "y te muestra el enlace directo para reservar.",
        parse_mode='Markdown'
    )


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛫 Alicante (ALC)", callback_data="origin_ALC"),
         InlineKeyboardButton("🛫 Murcia (RMU)", callback_data="origin_RMU")],
    ]
    await update.message.reply_text(
        "🔍 *Nueva búsqueda de vuelo*\n\n¿Desde qué aeropuerto salís?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ORIGIN


async def origin_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    origin_code = query.data.replace("origin_", "")
    context.user_data['origin'] = origin_code
    context.user_data['origin_name'] = AIRPORTS.get(origin_code, origin_code)

    # Teclado de destinos populares
    keyboard = []
    destinos = [
        ('LHR', '🇬🇧 Londres LHR'), ('STN', '🇬🇧 Londres STN'), ('LTN', '🇬🇧 Londres LTN'),
        ('CDG', '🇫🇷 París'), ('AMS', '🇳🇱 Ámsterdam'), ('FCO', '🇮🇹 Roma'),
        ('MXP', '🇮🇹 Milán'), ('BER', '🇩🇪 Berlín'), ('VIE', '🇦🇹 Viena'),
        ('ATH', '🇬🇷 Atenas'), ('LIS', '🇵🇹 Lisboa'), ('DUB', '🇮🇪 Dublín'),
        ('PRG', '🇨🇿 Praga'), ('BUD', '🇭🇺 Budapest'), ('PMI', '🇪🇸 Mallorca'),
    ]
    for i in range(0, len(destinos), 3):
        fila = destinos[i:i+3]
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"dest_{code}")
            for code, label in fila
        ])
    keyboard.append([InlineKeyboardButton("✏️ Escribir código IATA", callback_data="dest_manual")])

    await query.edit_message_text(
        f"✅ Origen: *{context.user_data['origin_name']}*\n\n¿A dónde queréis ir?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return DESTINATION


async def destination_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "dest_manual":
        await query.edit_message_text(
            f"✅ Origen: *{context.user_data['origin_name']}*\n\n"
            "Escribe el código IATA del destino (ej: `MAD`, `BCN`, `LGW`):",
            parse_mode='Markdown'
        )
        return DESTINATION

    dest_code = query.data.replace("dest_", "")
    context.user_data['destination'] = dest_code
    context.user_data['destination_name'] = AIRPORTS.get(dest_code, dest_code)

    await query.edit_message_text(
        f"✅ Origen: *{context.user_data['origin_name']}*\n"
        f"✅ Destino: *{context.user_data['destination_name']}*\n\n"
        "¿Qué día salís? Escribe la fecha en formato `DD/MM/AAAA`:",
        parse_mode='Markdown'
    )
    return DATE_OUT


async def destination_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    if len(code) != 3 or not code.isalpha():
        await update.message.reply_text(
            "❌ Código no válido. Debe ser 3 letras (ej: `MAD`). Inténtalo de nuevo:",
            parse_mode='Markdown'
        )
        return DESTINATION

    context.user_data['destination'] = code
    context.user_data['destination_name'] = AIRPORTS.get(code, code)

    await update.message.reply_text(
        f"✅ Destino: *{context.user_data['destination_name']} ({code})*\n\n"
        "¿Qué día salís? Escribe la fecha en formato `DD/MM/AAAA`:",
        parse_mode='Markdown'
    )
    return DATE_OUT


async def date_out_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        date = datetime.strptime(text, "%d/%m/%Y")
        if date.date() < datetime.today().date():
            raise ValueError("Fecha pasada")
        context.user_data['date_out'] = date.strftime("%Y-%m-%d")
        context.user_data['date_out_display'] = text
    except ValueError:
        await update.message.reply_text(
            "❌ Fecha no válida. Usa el formato `DD/MM/AAAA` y asegúrate de que sea una fecha futura:",
            parse_mode='Markdown'
        )
        return DATE_OUT

    keyboard = [
        [InlineKeyboardButton("Solo ida", callback_data="noreturm")],
    ]
    await update.message.reply_text(
        f"✅ Salida: *{text}*\n\n"
        "¿Cuándo volvéis? Escribe la fecha en formato `DD/MM/AAAA`\n"
        "O pulsa si es solo ida:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return DATE_IN


async def date_in_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        context.user_data['date_in'] = None
        context.user_data['date_in_display'] = 'Solo ida'
        await query.edit_message_text(
            f"✅ Salida: *{context.user_data['date_out_display']}* | Solo ida\n\n"
            "¿Cuántas personas viajáis? (2-20):",
            parse_mode='Markdown'
        )
        return PASSENGERS

    text = update.message.text.strip()
    try:
        date = datetime.strptime(text, "%d/%m/%Y")
        out = datetime.strptime(context.user_data['date_out'], "%Y-%m-%d")
        if date.date() <= out.date():
            raise ValueError("Vuelta antes de ida")
        context.user_data['date_in'] = date.strftime("%Y-%m-%d")
        context.user_data['date_in_display'] = text
    except ValueError:
        await update.message.reply_text(
            "❌ Fecha no válida. Debe ser posterior a la de salida. Usa `DD/MM/AAAA`:",
            parse_mode='Markdown'
        )
        return DATE_IN

    await update.message.reply_text(
        f"✅ Salida: *{context.user_data['date_out_display']}*\n"
        f"✅ Vuelta: *{text}*\n\n"
        "¿Cuántas personas viajáis? (2-20):",
        parse_mode='Markdown'
    )
    return PASSENGERS


async def passengers_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        n = int(text)
        if not 2 <= n <= 20:
            raise ValueError
        context.user_data['passengers'] = n
    except ValueError:
        await update.message.reply_text("❌ Introduce un número entre 2 y 20:")
        return PASSENGERS

    # Resumen y búsqueda
    d = context.user_data
    vuelta_txt = f"Vuelta: {d.get('date_in_display', 'Solo ida')}\n" if d.get('date_in') else "Solo ida\n"
    searching_msg = await update.message.reply_text(
        f"🔍 *Buscando vuelos...*\n\n"
        f"📍 {d['origin_name']} → {d['destination_name']}\n"
        f"📅 Salida: {d['date_out_display']}\n"
        f"📅 {vuelta_txt}"
        f"👥 {n} personas\n\n"
        f"_Buscando plazas disponibles para todo el grupo..._",
        parse_mode='Markdown'
    )

    # Llamada a Amadeus
    results = await search_flights(
        origin=d['origin'],
        destination=d['destination'],
        date_out=d['date_out'],
        date_in=d.get('date_in'),
        passengers=n
    )

    await searching_msg.delete()

    if not results:
        keyboard = [[InlineKeyboardButton("🔄 Nueva búsqueda", callback_data="nueva_busqueda")]]
        await update.message.reply_text(
            "😕 *No se encontraron vuelos* con plazas suficientes para el grupo.\n\n"
            "Prueba con otras fechas o destino.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    for msg, airline_name, deeplink in format_flight_message(results, d['origin'], d['destination'], d['date_out'], d.get('date_in'), n):
        keyboard = [[InlineKeyboardButton(f"🔗 Reservar en {airline_name} →", url=deeplink)]]
        await update.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    await update.message.reply_text(
        "💡 *¿Cómo reservar?*\n"
        "Pulsa el botón de la opción que más os guste. "
        "Se abrirá la web de la aerolínea con el vuelo ya seleccionado para completar la reserva.\n\n"
        "Usa /buscar para hacer otra búsqueda.",
        parse_mode='Markdown'
    )

    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Búsqueda cancelada. Usa /buscar para empezar de nuevo."
    )
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error:", exc_info=context.error)


def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("Falta la variable de entorno TELEGRAM_TOKEN")

    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("buscar", buscar)],
        states={
            ORIGIN: [CallbackQueryHandler(origin_selected, pattern="^origin_")],
            DESTINATION: [
                CallbackQueryHandler(destination_selected, pattern="^dest_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, destination_manual)
            ],
            DATE_OUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_out_received)],
            DATE_IN: [
                CallbackQueryHandler(date_in_received, pattern="^noreturm$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, date_in_received)
            ],
            PASSENGERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, passengers_received)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(conv_handler)
    app.add_error_handler(error_handler)

    logger.info("Bot iniciado...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
