import os
import io
import asyncio
import subprocess
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from PIL import Image, ImageDraw, ImageFont
from huggingface_hub import InferenceClient


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN")

IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"

VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
SCENE_SECONDS = 5
SCENE_COUNT = 6

BASE_DIR = Path("video_work")
BASE_DIR.mkdir(exist_ok=True)


# =========================================================
# USER DATA
# =========================================================

user_projects = {}

# پیام‌هایی که ربات می‌تواند برای پاک‌سازی دنبال کند
user_messages = {}


# =========================================================
# MESSAGE TRACKING
# =========================================================

def remember_message(user_id, message_id):
    if user_id not in user_messages:
        user_messages[user_id] = []

    user_messages[user_id].append(message_id)

    # فقط 100 پیام آخر
    user_messages[user_id] = user_messages[user_id][-100:]


async def send_message(update, text, **kwargs):

    user_id = update.effective_user.id

    message = await update.effective_chat.send_message(
        text=text,
        **kwargs
    )

    remember_message(user_id, message.message_id)

    return message


async def delete_old_messages(bot, chat_id, user_id):

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
# BUTTONS
# =========================================================

def main_keyboard():

    return InlineKeyboardMarkup([
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
    ])


# =========================================================
# FONT
# =========================================================

def get_font(size=42):

    fonts = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]

    for font in fonts:

        if os.path.exists(font):
            return ImageFont.truetype(font, size)

    return ImageFont.load_default()


# =========================================================
# PROJECT TYPE
# =========================================================

def detect_project_type(text):

    t = text.lower()

    advertising_words = [
        "تبلیغ",
        "تبلیغات",
        "فروش",
        "فروشگاه",
        "خرید",
        "برند",
        "advertising",
        "advertisement",
        "sell",
        "sale",
        "brand",
    ]

    education_words = [
        "آموزش",
        "یادگیری",
        "درس",
        "آموزشی",
        "teach",
        "education",
        "lesson",
        "learn",
        "tutorial",
    ]

    product_words = [
        "محصول",
        "کالا",
        "دستگاه",
        "اپلیکیشن",
        "برنامه",
        "سرویس",
        "product",
        "device",
        "app",
        "software",
        "service",
    ]

    if any(x in t for x in education_words):
        return "education"

    if any(x in t for x in product_words):
        return "product"

    if any(x in t for x in advertising_words):
        return "advertising"

    return "general"


# =========================================================
# STORYBOARD
# =========================================================

def create_storyboard(text):

    project_type = detect_project_type(text)

    if project_type == "advertising":

        scenes = [
            {
                "title": "شروع",
                "caption": "یک مشکل واقعی را نشان می‌دهیم",
                "visual": "cinematic commercial opening, realistic modern environment, a person facing a common problem, natural lighting, professional advertising photography",
            },
            {
                "title": "مشکل",
                "caption": "مشکل را واضح‌تر می‌کنیم",
                "visual": "realistic close-up of a person struggling with the problem, emotional but natural facial expression, cinematic commercial photography",
            },
            {
                "title": "راه‌حل",
                "caption": "راه‌حل وارد داستان می‌شود",
                "visual": "professional product or service presentation, realistic environment, attractive composition, premium commercial photography",
            },
            {
                "title": "استفاده",
                "caption": "نحوه استفاده را نشان می‌دهیم",
                "visual": "real person naturally using the product or service, realistic hands and environment, cinematic advertising scene",
            },
            {
                "title": "نتیجه",
                "caption": "نتیجه مثبت را نشان می‌دهیم",
                "visual": "happy satisfied customer after using the solution, natural smile, realistic lifestyle scene, cinematic commercial photography",
            },
            {
                "title": "پایان",
                "caption": "نمای نهایی تبلیغ",
                "visual": "beautiful premium hero shot, product or service as the main focus, clean professional background, cinematic advertising photography",
            },
        ]

    elif project_type == "product":

        scenes = [
            {
                "title": "معرفی",
                "caption": "محصول را معرفی می‌کنیم",
                "visual": "premium product hero shot, realistic studio photography, cinematic lighting, highly detailed",
            },
            {
                "title": "نیاز",
                "caption": "نیازی که محصول حل می‌کند",
                "visual": "realistic person experiencing a common everyday problem, natural environment, cinematic photography",
            },
            {
                "title": "استفاده",
                "caption": "محصول در حال استفاده",
                "visual": "real person using a modern product naturally, realistic environment, professional commercial photography",
            },
            {
                "title": "جزئیات",
                "caption": "نمای نزدیک از محصول",
                "visual": "detailed close-up product photography, realistic materials, premium commercial lighting",
            },
            {
                "title": "نتیجه",
                "caption": "رضایت مشتری",
                "visual": "happy customer enjoying the benefits of a product, realistic lifestyle, natural expression, cinematic photography",
            },
            {
                "title": "نمای نهایی",
                "caption": "محصول در بهترین حالت",
                "visual": "premium final hero shot of the product, clean elegant background, cinematic commercial photography",
            },
        ]

    elif project_type == "education":

        scenes = [
            {
                "title": "شروع آموزش",
                "caption": "موضوع را معرفی می‌کنیم",
                "visual": "friendly professional teacher explaining a topic, modern classroom or studio, realistic educational photography",
            },
            {
                "title": "مفهوم اصلی",
                "caption": "مفهوم اصلی را توضیح می‌دهیم",
                "visual": "teacher explaining an important concept using a simple visual demonstration, realistic
