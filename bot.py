import os
import asyncio
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

BASE_DIR = Path("video_work")
BASE_DIR.mkdir(exist_ok=True)

# ذخیره پروژه‌های کاربران
user_projects = {}

# ذخیره پیام‌هایی که ربات در طول اجرای خودش می‌بیند
user_messages = {}


# =========================================================
# MESSAGE MEMORY
# =========================================================

def remember_message(user_id, message_id):
    if user_id not in user_messages:
        user_messages[user_id] = []

    user_messages[user_id].append(message_id)

    # فقط 100 پیام آخر
    user_messages[user_id] = user_messages[user_id][-100:]


async def send_message(update, text, **kwargs):
    """
    ارسال پیام و ذخیره ID آن برای پاک کردن بعدی
    """

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    message = await update.effective_chat.send_message(
        text=text,
        **kwargs
    )

    remember_message(user_id, message.message_id)

    return message


async def delete_old_messages(bot, chat_id, user_id):
    """
    پاک کردن پیام‌هایی که ربات از زمان اجرای فعلی به خاطر دارد.
    """

    messages = user_messages.get(user_id, [])

    for message_id in messages:

        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )

        except Exception:
            pass

    user_messages[user_id] = []


# =========================================================
# KEYBOARD
# =========================================================

def main_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 شروع ساخت ویدیو",
                callback_data="start_video"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 شروع مجدد",
                callback_data="clear_project"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def after_idea_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "🎬 ساخت ویدیو",
                callback_data="make_video"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 ایده جدید",
                callback_data="start_video"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 شروع مجدد",
                callback_data="clear_project"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # پاک کردن پروژه قبلی
    user_projects.pop(user_id, None)

    # پاک کردن پیام‌های قبلی که ربات می‌شناسد
    await delete_old_messages(
        context.bot,
        chat_id,
        user_id
    )

    text = (
        "🎬 سلام!\n\n"
        "به ربات ساخت ویدیو خوش آمدی.\n\n"
        "برای شروع روی دکمه زیر بزن:"
    )

    message = await update.effective_chat.send_message(
        text=text,
        reply_markup=main_keyboard()
    )

    remember_message(
        user_id,
        message.message_id
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    # -----------------------------------------------------
    # START VIDEO
    # -----------------------------------------------------

    if query.data == "start_video":

        user_projects[user_id] = {
            "idea": None,
            "storyboard": None,
            "status": "waiting_for_idea"
        }

        await query.edit_message_text(
            text=(
                "🎬 ساخت ویدیو\n\n"
                "لطفاً ایده یا موضوع ویدیوت را بنویس.\n\n"
                "مثلاً:\n"
                "«یک ویدیوی جذاب درباره کشاورزی مدرن و "
                "استفاده از هوش مصنوعی در کشاورزی»"
            )
        )

        return

    # -----------------------------------------------------
    # CLEAR PROJECT
    # -----------------------------------------------------

    if query.data == "clear_project":

        user_projects.pop(user_id, None)

        await delete_old_messages(
            context.bot,
            query.message.chat_id,
            user_id
        )

        message = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                "🗑 پروژه قبلی پاک شد.\n\n"
                "برای شروع دوباره روی دکمه زیر بزن:"
            ),
            reply_markup=main_keyboard()
        )

        remember_message(
            user_id,
            message.message_id
        )

        return

    # -----------------------------------------------------
    # MAKE VIDEO
    # -----------------------------------------------------

    if query.data == "make_video":

        project = user_projects.get(user_id)

        if not project or not project.get("idea"):

            await query.edit_message_text(
                text=(
                    "⚠️ هنوز ایده‌ای دریافت نکرده‌ام.\n\n"
                    "لطفاً ابتدا ایده ویدیوت را ارسال کن."
                ),
                reply_markup=main_keyboard()
            )

            return

        await query.edit_message_text(
            text=(
                "⏳ درخواست ساخت ویدیو دریافت شد.\n\n"
                "⚠️ موتور ساخت تصویر هنوز فعال نشده است.\n\n"
                "فعلاً ارتباط ربات را تست می‌کنیم تا مطمئن شویم "
                "ربات بدون خطا کار می‌کند."
            )
        )

        return


# =========================================================
# IDEA HANDLER
# =========================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    # ذخیره پیام کاربر
    remember_message(
        user_id,
        update.message.message_id
    )

    text = update.message.text.strip()

    if not text:
        return

    # اگر پروژه‌ای وجود ندارد
    if user_id not in user_projects:

        await send_message(
            update,
            "لطفاً ابتدا /start را بزن."
        )

        return

    project = user_projects[user_id]

    # -----------------------------------------------------
    # انتظار برای ایده
    # -----------------------------------------------------

    if project.get("status") == "waiting_for_idea":

        project["idea"] = text
        project["status"] = "idea_received"

        # فعلاً یک استوری‌بورد ساده ایجاد می‌کنیم
        storyboard = [
            {
                "scene": 1,
                "description": f"شروع ویدیو درباره: {text}"
            },
            {
                "scene": 2,
                "description": f"نمایش موضوع اصلی: {text}"
            },
            {
                "scene": 3,
                "description": f"توضیح مهم درباره: {text}"
            },
            {
                "scene": 4,
                "description": f"یک مثال واقعی درباره: {text}"
            },
            {
                "scene": 5,
                "description": f"جمع‌بندی موضوع: {text}"
            },
            {
                "scene": 6,
                "description": f"پایان ویدیو درباره: {text}"
            }
        ]

        project["storyboard"] = storyboard

        response = (
            "✅ ایده دریافت شد!\n\n"
            f"💡 ایده:\n{text}\n\n"
            "📋 سناریوی اولیه آماده شد:\n\n"
            "🎬 صحنه 1 — شروع موضوع\n"
            "🎬 صحنه 2 — معرفی موضوع\n"
            "🎬 صحنه 3 — توضیح اصلی\n"
            "🎬 صحنه 4 — مثال\n"
            "🎬 صحنه 5 — جمع‌بندی\n"
            "🎬 صحنه 6 — پایان\n\n"
            "حالا می‌توانیم وارد مرحله ساخت ویدیو شویم."
        )

        await send_message(
            update,
            response,
            reply_markup=after_idea_keyboard()
        )

        return

    # -----------------------------------------------------
    # اگر ایده قبلاً دریافت شده
    # -----------------------------------------------------

    if project.get("status") == "idea_received":

        project["idea"] = text

        await send_message(
            update,
            (
                "✅ ایده جدید جایگزین شد.\n\n"
                f"💡 {text}\n\n"
                "برای ادامه روی «🎬 ساخت ویدیو» بزن."
            ),
            reply_markup=after_idea_keyboard()
        )

        return

    # -----------------------------------------------------
    # وضعیت نامشخص
    # -----------------------------------------------------

    await send_message(
        update,
        (
            "پیامت دریافت شد ✅\n\n"
            "برای شروع یک پروژه جدید، /start را بزن."
        ),
        reply_markup=main_keyboard()
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):

    print("====================================")
    print("BOT ERROR")
    print("====================================")

    try:
        print(context.error)
    except Exception:
        pass

    print("====================================")


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        print("ERROR: BOT_TOKEN is not set.")
        return

    print("====================================")
    print("AI VIDEO TELEGRAM BOT")
    print("Starting...")
    print("====================================")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # Buttons
    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # Text
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    # Errors
    application.add_error_handler(
        error_handler
    )

    print("Bot is running...")
    print("Waiting for Telegram messages...")

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
