# water_order_bot.py

import logging
import re
from datetime import datetime

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# -------------------- НАСТРОЙКИ --------------------
BOT_TOKEN = "8076676164:AAHDTOzxedkQd0dyUpKBgd4yJ25xyiPSEiI"
OWNER_CHAT_ID = 7258655708  # Example: 123456789
GOOGLE_SHEET_NAME = "WaterOrders"  # Название вашей таблицы
REGION_COURIERS = {
    "сино": [111111111],
    "сомони": [222222222],
    "фирдавси": [333333333],
}

# Убедитесь, что вы заменили BOT_TOKEN и OWNER_CHAT_ID на реальные значения выше.

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ASK_LANG, ASK_ADDRESS, ASK_PHONE, ASK_QUANTITY, CONFIRM = range(5)

# -------------------- GOOGLE SHEETS --------------------
async def save_to_google_sheets(data, context=None):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open(GOOGLE_SHEET_NAME).sheet1
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("username", "—"),
            data["phone"],
            data["address"],
            data["quantity"],
            data.get("lang", "ru"),
            data.get("region", "неизвестно")
        ])
    except Exception as e:
        logger.error(f"Ошибка сохранения в Google Sheets: {e}")
        if context is not None:
            try:
                await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=f"❗ Ошибка Google Sheets: {e}")
            except Exception as err:
                logger.error(f"Ошибка отправки сообщения владельцу: {err}")

# -------------------- ХЭЛПЕР --------------------
def get_region(address):
    address = address.lower()
    for region in REGION_COURIERS:
        if region in address:
            return region
    return None

# Словари сообщений для мультиязычности
MESSAGES = {
    "choose_lang": {
        "ru": "Выберите язык / Забони худро интихоб кунед:",
        "tj": "Забони худро интихоб кунед / Выберите язык:"
    },
    "press_order": {
        "ru": 'Нажмите кнопку "Заказать":',
        "tj": 'Тугмаи "Фармоиш додан"-ро пахш кунед:'
    },
    "enter_address": {
        "ru": "📍 Введите адрес доставки:",
        "tj": "📍 Нишонии расониданро ворид кунед:"
    },
    "enter_phone": {
        "ru": "📞 Введите номер телефона (9 цифр):",
        "tj": "📞 Рақами телефонро ворид кунед (9 рақам):"
    },
    "phone_error": {
        "ru": "❌ Номер должен содержать 9 цифр. Попробуйте снова:",
        "tj": "❌ Рақам бояд 9 рақам бошад. Аз нав кӯшиш кунед:"
    },
    "enter_quantity": {
        "ru": "💧 Сколько бутылей по 19л вы хотите заказать?",
        "tj": "💧 Чанд бутлии 19-литра фармоиш медиҳед?"
    },
    "quantity_error": {
        "ru": "❌ Введите корректное число (> 0)",
        "tj": "❌ Рақами дурустро ворид кунед (> 0)"
    },
    "order_confirm": {
        "ru": "✅ Ваш заказ:\n📍 Адрес: {address}\n📞 Телефон: {phone}\n💧 Кол-во: {quantity} бутылей по 19л\n📦 Район: {region}\nОтправить заказ? (Да / Нет)",
        "tj": "✅ Фармоиши шумо:\n📍 Нишонӣ: {address}\n📞 Телефон: {phone}\n💧 Миқдор: {quantity} бутлии 19л\n📦 Ноҳия: {region}\nФармоишро фиристед? (Ҳа / Не)"
    },
    "order_sent": {
        "ru": "✅ Заказ отправлен! Спасибо!",
        "tj": "✅ Фармоиш фиристода шуд! Ташаккур!"
    },
    "order_cancel": {
        "ru": "❌ Заказ отменён.",
        "tj": "❌ Фармоиш бекор шуд."
    },
}

# -------------------- ХЭНДЛЕРЫ --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🇷🇺 Русский"], ["🇹🇯 Тоҷикӣ"]]
    await update.message.reply_text(
        MESSAGES["choose_lang"]["ru"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ASK_LANG

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = "ru" if "рус" in update.message.text.lower() else "tj"
    context.user_data["lang"] = lang
    label = "Заказать" if lang == "ru" else "Фармоиш додан"
    await update.message.reply_text(
        MESSAGES["press_order"][lang],
        reply_markup=ReplyKeyboardMarkup([[label]], resize_keyboard=True)
    )
    return ASK_ADDRESS

async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data["lang"]
    if (lang == "ru" and "заказать" in update.message.text.lower()) or \
       (lang == "tj" and "фармоиш" in update.message.text.lower()):
        await update.message.reply_text(
            MESSAGES["enter_address"][lang],
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_PHONE
    else:
        return ASK_ADDRESS

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    region = get_region(update.message.text)
    context.user_data["region"] = region
    lang = context.user_data["lang"]
    await update.message.reply_text(MESSAGES["enter_phone"][lang])
    return ASK_QUANTITY

async def ask_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    lang = context.user_data["lang"]
    if not re.fullmatch(r"\d{9}", phone):
        await update.message.reply_text(MESSAGES["phone_error"][lang])
        return ASK_QUANTITY
    context.user_data["phone"] = phone
    await update.message.reply_text(MESSAGES["enter_quantity"][lang])
    return CONFIRM

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data["lang"]
    try:
        quantity = int(update.message.text)
        if quantity <= 0:
            raise ValueError
        context.user_data["quantity"] = quantity
    except ValueError:
        await update.message.reply_text(MESSAGES["quantity_error"][lang])
        return CONFIRM

    data = context.user_data
    msg = MESSAGES["order_confirm"][lang].format(
        address=data["address"],
        phone=data["phone"],
        quantity=data["quantity"],
        region=data.get("region", "неизвестно")
    )
    btns = [["Да", "Нет"]] if lang == "ru" else [["Ҳа", "Не"]]
    await update.message.reply_text(
        msg,
        reply_markup=ReplyKeyboardMarkup(btns, resize_keyboard=True)
    )
    return ConversationHandler.END

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    text = update.message.text.lower()
    if (lang == "ru" and "да" in text) or (lang == "tj" and "ҳа" in text):
        data = context.user_data
        user = update.effective_user
        data["username"] = user.username or user.first_name

        # Отправка владельцу
        msg = (f"🚨 Новый заказ от @{data['username']}:\n"
               f"📍 {data['address']}\n"
               f"📞 {data['phone']}\n"
               f"💧 {data['quantity']} бутылей\n")
        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=msg)

        # Отправка курьерам по району
        region = data.get("region")
        if region and region in REGION_COURIERS:
            for courier_id in REGION_COURIERS[region]:
                await context.bot.send_message(chat_id=courier_id, text=msg)

        # Сохраняем в Google Sheets
        await save_to_google_sheets(data, context)
        await update.message.reply_text(
            MESSAGES["order_sent"][lang],
            reply_markup=ReplyKeyboardMarkup([["Заново"]], resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            MESSAGES["order_cancel"][lang],
            reply_markup=ReplyKeyboardMarkup([["Заново"]], resize_keyboard=True)
        )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    await update.message.reply_text(MESSAGES["order_cancel"][lang], reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# -------------------- ЗАПУСК --------------------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.Regex("^Заново$"), start)],
        states={
            ASK_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_language)],
            ASK_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_address)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            ASK_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_quantity)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("^(Да|Нет|Ҳа|Не)$"), handle_confirmation))
    app.add_handler(MessageHandler(filters.Regex("^Заново$"), start))

    app.run_polling()

if __name__ == '__main__':
    main()
