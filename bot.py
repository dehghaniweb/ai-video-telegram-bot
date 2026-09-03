import os
import re
import time
import json
import shutil
import subprocess
import requests

from PIL import Image, ImageOps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]

HORDE_API = "https://aihorde.net/api/v2"
HORDE_KEY = "0000000000"
CLIENT_AGENT = "AliDeghani-AI-Video-Bot/1.0"

BASE_DIR = "video_data"


# =========================================================
# پوشه کاربر
# =========================================================

def get_chat_dir(chat_id):
    path = os.path.join(BASE_DIR, str(chat_id))
    os.makedirs(path, exist_ok=True)
    return path


# =========================================================
# تشخیص نوع محصول
# =========================================================

def detect_subject(text):
    t = text.lower()

    agriculture = [
        "کود", "گیاه", "کشاورزی", "گندم", "جو", "ذرت",
        "مزرعه", "کشاورز", "fertilizer", "wheat",
        "agriculture", "farm", "crop"
    ]

    grooming = [
        "ماشین اصلاح", "ریش تراش", "اصلاح صورت",
        "شیور", "موزر", "shaver", "trimmer", "grooming"
    ]

    shoes = [
        "کفش", "کتانی", "sneaker", "shoe", "running"
    ]

    electronics = [
        "موبایل", "گوشی", "تلفن", "لپ تاپ", "تبلت",
        "کامپیوتر", "هدفون", "phone", "smartphone",
        "laptop", "tablet", "headphone"
    ]

    perfume = [
        "عطر", "ادکلن", "perfume", "cologne"
    ]

    food = [
        "غذا", "خوراکی", "شکلات", "قهوه", "نوشیدنی",
        "food", "coffee", "chocolate", "drink"
    ]

    cosmetics = [
        "کرم", "لوازم آرایش", "آرایش", "شامپو",
        "cosmetic", "cream", "shampoo", "makeup"
    ]

    for word in agriculture:
        if word in t:
            return "agriculture"

    for word in grooming:
        if word in t:
            return "grooming"

    for word in shoes:
        if word in t:
            return "shoes"

    for word in electronics:
        if word in t:
            return "electronics"

    for word in perfume:
        if word in t:
            return "perfume"

    for word in food:
        if word in t:
            return "food"

    for word in cosmetics:
        if word in t:
            return "cosmetics"

    return "general"


# =========================================================
# صحنه های تبلیغاتی
# =========================================================

SCENES = {
    "agriculture": [
        "wide cinematic wheat field at sunrise, farmer inspecting healthy crops",
        "close-up of healthy green wheat plants in a professional agricultural field",
        "farmer applying plant fertilizer carefully to wheat crops",
        "modern agricultural field with strong healthy wheat plants and professional farming equipment",
        "farmer standing proudly inside a beautiful productive wheat field",
        "premium agricultural product advertisement, healthy crops, professional farm atmosphere"
    ],

    "grooming": [
        "modern luxury bathroom, handsome male model preparing for shaving",
        "close-up professional electric shaver being used on a man's face",
        "modern grooming scene with clean skin and premium grooming device",
        "stylish bathroom counter with premium electric shaver and grooming accessories",
        "confident man after shaving, clean professional appearance",
        "premium commercial advertisement for an electric face shaver"
    ],

    "shoes": [
        "professional athlete running outdoors wearing premium athletic shoes",
        "close-up of modern running shoes during athletic movement",
        "beautiful sports track with athlete wearing the advertised shoes",
        "urban lifestyle scene with fashionable athletic shoes",
        "athlete confidently finishing a run wearing premium shoes",
        "premium sports shoe commercial, dynamic professional advertising photography"
    ],

    "electronics": [
        "modern technology lifestyle scene with a premium smartphone",
        "close-up of a modern smartphone with beautiful screen and reflections",
        "professional person using a premium smartphone in a modern office",
        "smartphone on a stylish desk surrounded by modern technology",
        "young professional using smartphone in an elegant modern environment",
        "premium technology commercial advertisement"
    ],

    "perfume": [
        "luxury perfume bottle in an elegant black and gold environment",
        "close-up premium perfume bottle with dramatic studio lighting",
        "luxury fashion environment with elegant perfume product",
        "premium perfume bottle surrounded by beautiful reflections",
        "luxury lifestyle scene with elegant fragrance product",
        "high-end perfume commercial advertisement"
    ],

    "food": [
        "beautiful premium food photography in a modern restaurant",
        "close-up delicious food with cinematic lighting",
        "happy family enjoying the advertised food product",
        "modern kitchen with premium food product",
        "professional food advertisement with appetizing presentation",
        "premium commercial food photography"
    ],

    "cosmetics": [
        "luxury beauty studio with premium cosmetic product",
        "close-up elegant cosmetic product with soft professional lighting",
        "beautiful woman using premium cosmetic product",
        "luxury bathroom with premium beauty products",
        "professional beauty advertisement photography",
        "premium cosmetics commercial"
    ],

    "general": [
        "premium commercial product photography in a modern environment",
        "close-up product advertisement with cinematic lighting",
        "professional person using the advertised product",
        "modern lifestyle scene featuring the advertised product",
        "beautiful premium advertising scene",
        "high-end commercial product photography"
    ]
}


# =========================================================
# ساخت پرامپت
# =========================================================

def create_prompt(idea, category, scene, index):
    return f"""
Create a professional commercial advertising photograph.

Product/service description:
{idea}

Product category:
{category}

Scene:
{scene}

This is advertisement image number {index} of a coherent advertising campaign.

Important:
- Make the advertised product the main subject.
- The image must clearly relate to the user's product.
- Keep the same product concept throughout the campaign.
- Realistic professional photography.
- Cinematic lighting.
- Premium commercial advertising quality.
- Natural realistic people when people are needed.
- Vertical composition suitable for a smartphone advertisement video.
- No unrelated objects.
- No random people posing without connection to the product.
- No text.
- No logos.
- No watermark.
"""


# =========================================================
# AI HORDE
# =========================================================

def horde_headers():
    return {
        "apikey": HORDE_KEY,
        "Client-Agent": CLIENT_AGENT,
        "Content-Type": "application/json",
    }


def generate_horde_image(prompt, output_file):
    payload = {
        "prompt": prompt,
        "params": {
            "width": 576,
            "height": 1024,
            "steps": 20,
            "cfg_scale": 7,
            "n": 1
        },
        "nsfw": False,
        "censor_nsfw": True
    }

    response = requests.post(
        f"{HORDE_API}/generate/async",
        headers=horde_headers(),
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    job_id = data.get("id")

    if not job_id:
        raise Exception(f"Horde job ID not found: {data}")

    print("Horde Job:", job_id)

    start_time = time.time()

    while True:

        if time.time() - start_time > 900:
            raise Exception("AI Horde timeout")

        status_response = requests.get(
            f"{HORDE_API}/generate/status/{job_id}",
            headers=horde_headers(),
            timeout=60
        )

        status_response.raise_for_status()

        status = status_response.json()

        print("Horde status:", status)

        if status.get("faulted"):
            raise Exception("AI Horde generation failed")

        if status.get("done"):
            generations = status.get("generations", [])

            if not generations:
                raise Exception("Horde returned no image")

            image_url = generations[0].get("img")

            if not image_url:
                raise Exception("Horde image URL missing")

            image_response = requests.get(
                image_url,
                timeout=120
            )

            image_response.raise_for_status()

            with open(output_file, "wb") as f:
                f.write(image_response.content)

            return output_file

        time.sleep(5)


# =========================================================
# آماده سازی تصویر
# =========================================================

def prepare_image(path, size=(720, 1280)):
    img = Image.open(path).convert("RGB")

    img = ImageOps.fit(
        img,
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5)
    )

    img.save(path, quality=95)


# =========================================================
# ساخت ویدیو
# =========================================================

def create_video_from_images(image_files, output_file, duration):
    temp_dir = os.path.join(
        os.path.dirname(output_file),
        "frames"
    )

    os.makedirs(temp_dir, exist_ok=True)

    for i, image_file in enumerate(image_files):
        frame_path = os.path.join(
            temp_dir,
            f"frame_{i:03d}.jpg"
        )

        img = Image.open(image_file).convert("RGB")

        img = ImageOps.fit(
            img,
            (720, 1280),
            method=Image.Resampling.LANCZOS
        )

        img.save(frame_path, quality=92)

    seconds_per_image = duration / len(image_files)

    concat_file = os.path.join(
        temp_dir,
        "concat.txt"
    )

    with open(concat_file, "w", encoding="utf-8") as f:
        for i in range(len(image_files)):
            frame_path = os.path.abspath(
                os.path.join(
                    temp_dir,
                    f"frame_{i:03d}.jpg"
                )
            )

            f.write(
                f"file '{frame_path}'\n"
            )

            f.write(
                f"duration {seconds_per_image}\n"
            )

        last_frame = os.path.abspath(
            os.path.join(
                temp_dir,
                f"frame_{len(image_files)-1:03d}.jpg"
            )
        )

        f.write(
            f"file '{last_frame}'\n"
        )

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-vf",
        "scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280",
        "-r",
        "24",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "27",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_file
    ]

    subprocess.run(
        command,
        check=True
    )

    shutil.rmtree(
        temp_dir,
        ignore_errors=True
    )

    return output_file


# =========================================================
# تنظیمات
# =========================================================

def save_settings(chat_id, settings):
    path = os.path.join(
        get_chat_dir(chat_id),
        "settings.json"
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            settings,
            f,
            ensure_ascii=False,
            indent=2
        )


def load_settings(chat_id):
    path = os.path.join(
        get_chat_dir(chat_id),
        "settings.json"
    )

    if not os.path.exists(path):
        return {
            "duration": 30,
            "images": 6,
            "idea": ""
        }

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# /start
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "🎬 ساخت تبلیغ جدید",
                callback_data="new_video"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 شروع مجدد",
                callback_data="restart"
            )
        ]
    ]

    await update.message.reply_text(
        "🤖 ربات ساخت ویدیوی تبلیغاتی آماده است.\n\n"
        "مثلاً بنویس:\n"
        "«تبلیغ کود گیاهی برای گندم»\n\n"
        "یا:\n"
        "«تبلیغ ماشین اصلاح صورت»",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# دکمه ها
# =========================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id

    if query.data == "restart":

        chat_dir = get_chat_dir(chat_id)

        for name in os.listdir(chat_dir):
            path = os.path.join(chat_dir, name)

            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    os.remove(path)
                except:
                    pass

        await query.message.reply_text(
            "🔄 شروع مجدد انجام شد.\n\n"
            "حالا توضیح تبلیغت را بفرست."
        )

        return

    if query.data == "new_video":

        save_settings(
            chat_id,
            {
                "duration": 30,
                "images": 6,
                "idea": ""
            }
        )

        await query.message.reply_text(
            "📝 توضیح محصول یا تبلیغ را بفرست."
        )


# =========================================================
# دریافت متن
# =========================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    text = update.message.text.strip()

    settings = load_settings(chat_id)

    settings["idea"] = text

    save_settings(chat_id, settings)

    keyboard = [
        [
            InlineKeyboardButton("30 ثانیه", callback_data="dur_30"),
            InlineKeyboardButton("45 ثانیه", callback_data="dur_45"),
            InlineKeyboardButton("60 ثانیه", callback_data="dur_60")
        ],
        [
            InlineKeyboardButton("6 تصویر", callback_data="img_6"),
            InlineKeyboardButton("9 تصویر", callback_data="img_9"),
            InlineKeyboardButton("12 تصویر", callback_data="img_12")
        ],
        [
            InlineKeyboardButton(
                "🎬 ساخت ویدیو",
                callback_data="build"
            )
        ]
    ]

    await update.message.reply_text(
        "✅ توضیح تبلیغ دریافت شد.\n\n"
        "⏱ مدت ویدیو را انتخاب کن و سپس تعداد تصاویر را مشخص کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# تنظیمات دکمه ای
# =========================================================

async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    settings = load_settings(chat_id)

    data = query.data

    if data.startswith("dur_"):
        settings["duration"] = int(
            data.replace("dur_", "")
        )

        save_settings(chat_id, settings)

        await query.message.reply_text(
            f"⏱ مدت انتخاب شد: {settings['duration']} ثانیه"
        )

        return

    if data.startswith("img_"):
        settings["images"] = int(
            data.replace("img_", "")
        )

        save_settings(chat_id, settings)

        await query.message.reply_text(
            f"🖼 تعداد تصاویر: {settings['images']}"
        )

        return

    if data == "build":

        if not settings.get("idea"):
            await query.message.reply_text(
                "❌ ابتدا توضیح تبلیغ را بفرست."
            )
            return

        await build_video(
            query,
            settings
        )


# =========================================================
# ساخت ویدیو
# =========================================================

async def build_video(query, settings):

    chat_id = query.message.chat_id
    idea = settings["idea"]
    duration = int(settings["duration"])
    image_count = int(settings["images"])

    category = detect_subject(idea)

    chat_dir = get_chat_dir(chat_id)

    # پاک کردن تصاویر قبلی
    for name in os.listdir(chat_dir):
        if name.startswith("image_") and name.endswith(".jpg"):
            try:
                os.remove(
                    os.path.join(chat_dir, name)
                )
            except:
                pass

    await query.message.reply_text(
        f"🚀 ساخت تبلیغ شروع شد.\n\n"
        f"📌 محصول: {idea}\n"
        f"📂 دسته: {category}\n"
        f"🖼 تصاویر: {image_count}\n"
        f"⏱ زمان: {duration} ثانیه\n\n"
        f"⏳ تولید تصاویر با AI Horde شروع شد..."
    )

    image_files = []

    scenes = SCENES.get(
        category,
        SCENES["general"]
    )

    for i in range(image_count):

        scene = scenes[i % len(scenes)]

        prompt = create_prompt(
            idea,
            category,
            scene,
            i + 1
        )

        output_file = os.path.join(
            chat_dir,
            f"image_{i+1:03d}.jpg"
        )

        try:

            await query.message.reply_text(
                f"🖼 تصویر {i+1}/{image_count} در حال تولید است..."
            )

            generate_horde_image(
                prompt,
                output_file
            )

            prepare_image(output_file)

            image_files.append(output_file)

            print(
                f"Image {i+1} created: {output_file}"
            )

        except Exception as e:

            print(
                "IMAGE ERROR:",
                repr(e)
            )

            await query.message.reply_text(
                f"⚠️ تصویر {i+1} ساخته نشد.\n"
                f"در حال تلاش مجدد..."
            )

            try:

                generate_horde_image(
                    prompt + "\nHigh quality realistic commercial photography.",
                    output_file
                )

                prepare_image(output_file)

                image_files.append(
                    output_file
                )

            except Exception as e2:

                print(
                    "RETRY ERROR:",
                    repr(e2)
                )

    if len(image_files) < 2:

        await query.message.reply_text(
            "❌ تصاویر کافی برای ساخت ویدیو تولید نشد.\n"
            "احتمالاً صف AI Horde شلوغ است."
        )

        return

    await query.message.reply_text(
        "🎬 تصاویر آماده شدند.\n"
        "در حال ساخت ویدیوی نهایی..."
    )

    video_file = os.path.join(
        chat_dir,
        "advertising_video.mp4"
    )

    try:

        create_video_from_images(
            image_files,
            video_file,
            duration
        )

    except Exception as e:

        print(
            "VIDEO ERROR:",
            repr(e)
        )

        await query.message.reply_text(
            "❌ خطا هنگام ساخت ویدیو."
        )

        return

    await query.message.reply_text(
        "✅ ویدیو آماده شد.\n"
        "📤 در حال ارسال..."
    )

    try:

        with open(video_file, "rb") as video:

            await query.message.reply_video(
                video=video,
                caption=(
                    "🎬 تبلیغ آماده شد\n\n"
                    f"⏱ {duration} ثانیه\n"
                    f"🖼 {len(image_files)} تصویر\n"
                    f"📌 {idea}"
                ),
                supports_streaming=True
            )

    except Exception as e:

        print(
            "TELEGRAM VIDEO ERROR:",
            repr(e)
        )

        await query.message.reply_text(
            "❌ ارسال ویدیو به تلگرام ناموفق بود."
        )


# =========================================================
# MAIN
# =========================================================

def main():

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern="^(restart|new_video)$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            settings_handler,
            pattern="^(dur_|img_|build)"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler
        )
    )

    print("BOT STARTED")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
