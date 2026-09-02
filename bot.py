import os
import io
import asyncio
import subprocess
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
        "محصول",
        "advertising",
        "advertisement",
        "sell",
        "sale",
        "product",
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
                "visual": "teacher explaining an important concept using a simple visual demonstration, realistic classroom",
            },
            {
                "title": "مثال",
                "caption": "یک مثال واقعی",
                "visual": "step by step educational demonstration, realistic hands and objects, clear composition, professional photography",
            },
            {
                "title": "تمرین",
                "caption": "تمرین عملی",
                "visual": "student practicing the learned concept, realistic educational environment, natural lighting",
            },
            {
                "title": "نتیجه",
                "caption": "نتیجه یادگیری",
                "visual": "successful student understanding the lesson, positive natural expression, realistic educational photography",
            },
            {
                "title": "پایان",
                "caption": "جمع‌بندی آموزش",
                "visual": "professional educational studio scene, teacher confidently concluding the lesson, cinematic realistic photography",
            },
        ]

    else:

        scenes = [
            {
                "title": "شروع",
                "caption": "شروع داستان",
                "visual": "cinematic realistic opening scene related to the subject, natural environment, professional photography",
            },
            {
                "title": "موضوع",
                "caption": "معرفی موضوع",
                "visual": "realistic scene clearly showing the main subject, cinematic composition",
            },
            {
                "title": "توضیح",
                "caption": "توضیح بخش مهم",
                "visual": "realistic detailed scene related to the subject, natural lighting, cinematic photography",
            },
            {
                "title": "جزئیات",
                "caption": "نمای نزدیک",
                "visual": "cinematic close-up related to the subject, highly detailed realistic photography",
            },
            {
                "title": "نتیجه",
                "caption": "نتیجه داستان",
                "visual": "positive realistic outcome related to the subject, natural people and environment",
            },
            {
                "title": "پایان",
                "caption": "نمای نهایی",
                "visual": "beautiful cinematic final scene related to the subject, professional realistic photography",
            },
        ]

    return project_type, scenes


# =========================================================
# GENERATE IMAGE
# =========================================================

def generate_image(prompt):

    client = InferenceClient(
        provider="auto",
        api_key=HF_TOKEN
    )

    negative_prompt = (
        "blurry, low quality, distorted face, extra fingers, "
        "extra limbs, deformed hands, text, watermark, logo, "
        "cartoon, anime, illustration"
    )

    image = client.text_to_image(
        prompt=prompt,
        model=IMAGE_MODEL,
        negative_prompt=negative_prompt
    )

    return image


# =========================================================
# PREPARE IMAGE
# =========================================================

def prepare_image(image, caption, output_file):

    image = image.convert("RGB")

    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
    image_ratio = image.width / image.height

    if image_ratio > target_ratio:

        new_width = int(image.height * target_ratio)
        left = (image.width - new_width) // 2

        image = image.crop(
            (
                left,
                0,
                left + new_width,
                image.height
            )
        )

    else:

        new_height = int(image.width / target_ratio)
        top = (image.height - new_height) // 2

        image = image.crop(
            (
                0,
                top,
                image.width,
                top + new_height
            )
        )

    image = image.resize(
        (VIDEO_WIDTH, VIDEO_HEIGHT),
        Image.Resampling.LANCZOS
    )

    draw = ImageDraw.Draw(image)

    font = get_font(40)

    margin = 35
    max_width = VIDEO_WIDTH - 2 * margin

    words = caption.split()
    lines = []
    current = ""

    for word in words:

        test = current + " " + word

        bbox = draw.textbbox(
            (0, 0),
            test,
            font=font
        )

        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current.strip())

            current = word

    if current:
        lines.append(current.strip())

    line_height = 55
    box_height = len(lines) * line_height + 45

    box_top = VIDEO_HEIGHT - box_height - 50

    draw.rounded_rectangle(
        (
            margin,
            box_top,
            VIDEO_WIDTH - margin,
            VIDEO_HEIGHT - 50
        ),
        radius=25,
        fill=(0, 0, 0)
    )

    y = box_top + 20

    for line in lines:

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font
        )

        text_width = bbox[2] - bbox[0]

        x = (VIDEO_WIDTH - text_width) // 2

        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 255, 255)
        )

        y += line_height

    image.save(output_file, quality=95)


# =========================================================
# CREATE VIDEO
# =========================================================

def create_video(image_files, output_file, audio_file=None):

    work_dir = output_file.parent

    clips = []

    for i, image_file in enumerate(image_files):

        clip = work_dir / f"scene_{i}.mp4"

        zoom_direction = "in"

        if i % 2 == 1:
            zoom_direction = "out"

        if zoom_direction == "in":

            vf = (
                "scale=720:1280,"
                "zoompan="
                "z='min(zoom+0.0008,1.12)':"
                "x='iw/2-(iw/zoom/2)':"
                "y='ih/2-(ih/zoom/2)':"
                "d=150:"
                "s=720x1280:"
                "fps=30"
            )

        else:

            vf = (
                "scale=720:1280,"
                "zoompan="
                "z='if(eq(on,1),1.12,max(zoom-0.0008,1.0))':"
                "x='iw/2-(iw/zoom/2)':"
                "y='ih/2-(ih/zoom/2)':"
                "d=150:"
                "s=720x1280:"
                "fps=30"
            )

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_file),
            "-vf",
            vf,
            "-t",
            str(SCENE_SECONDS),
            "-r",
            "30",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(clip)
        ]

        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        clips.append(clip)

    concat_file = work_dir / "concat.txt"

    with open(concat_file, "w", encoding="utf-8") as f:

        for clip in clips:
            f.write(f"file '{clip.resolve()}'\n")

    silent_video = work_dir / "silent.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(silent_video)
    ]

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if audio_file and audio_file.exists():

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(audio_file),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_file)
        ]

        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    else:

        silent_video.replace(output_file)


# =========================================================
# /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    user_projects.pop(user_id, None)

    await update.message.reply_text(
        "🎬 سلام!\n\n"
        "ایده ویدیویی خودت را برای من بنویس.\n\n"
        "مثلاً:\n"
        "«برای یک کود گیاهی تبلیغ بساز که به کشاورزان معرفی شود.»\n\n"
        "یا:\n"
        "«یک ویدیوی آموزشی درباره نحوه نگهداری گل بساز.»\n\n"
        "بعد از ساخت سناریو، با دستور /render ویدیو ساخته می‌شود."
    )


# =========================================================
# /CLEAR
# =========================================================

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    user_projects.pop(user_id, None)

    await update.message.reply_text(
        "🗑 پروژه پاک شد.\n\n"
        "حالا ایده جدیدت را بفرست."
    )


# =========================================================
# TEXT
# =========================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    text = update.message.text.strip()

    if not text:
        return

    project_type, scenes = create_storyboard(text)

    user_projects[user_id] = {
        "text": text,
        "type": project_type,
        "scenes": scenes,
        "photo": None,
        "audio": None,
    }

    message = "🎬 سناریوی پیشنهادی آماده شد:\n\n"

    for i, scene in enumerate(scenes, 1):

        message += (
            f"🎞 صحنه {i}: {scene['title']}\n"
            f"📝 {scene['caption']}\n\n"
        )

    message += (
        "اگر سناریو را می‌پسندی، دستور زیر را بفرست:\n\n"
        "👉 /render\n\n"
        "برای شروع پروژه جدید:\n"
        "👉 /clear"
    )

    await update.message.reply_text(message)


# =========================================================
# PHOTO
# =========================================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if user_id not in user_projects:

        await update.message.reply_text(
            "اول ایده ویدیویی را به صورت متن بفرست."
        )

        return

    photo = update.message.photo[-1]

    file = await context.bot.get_file(photo.file_id)

    photo_path = BASE_DIR / f"user_{user_id}_photo.jpg"

    await file.download_to_drive(photo_path)

    user_projects[user_id]["photo"] = photo_path

    await update.message.reply_text(
        "📷 عکس دریافت شد.\n\n"
        "فعلاً در تولید تصویر به عنوان مرجع پروژه ذخیره شده است.\n"
        "حالا /render را بفرست."
    )


# =========================================================
# AUDIO
# =========================================================

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if user_id not in user_projects:

        await update.message.reply_text(
            "اول ایده ویدیویی را بفرست."
        )

        return

    audio = update.message.audio or update.message.voice

    if not audio:
        return

    file = await context.bot.get_file(audio.file_id)

    audio_path = BASE_DIR / f"user_{user_id}_audio.ogg"

    await file.download_to_drive(audio_path)

    user_projects[user_id]["audio"] = audio_path

    await update.message.reply_text(
        "🎵 فایل صوتی دریافت شد.\n"
        "در خروجی ویدیو استفاده می‌شود."
    )


# =========================================================
# /RENDER
# =========================================================

async def render(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if user_id not in user_projects:

        await update.message.reply_text(
            "❗ ابتدا ایده ویدیویی خودت را بفرست."
        )

        return

    if not HF_TOKEN:

        await update.message.reply_text(
            "❌ توکن Hugging Face پیدا نشد.\n\n"
            "بررسی کن Secret زیر در GitHub ساخته شده باشد:\n"
            "HF_TOKEN"
        )

        return

    project = user_projects[user_id]

    await update.message.reply_text(
        "⏳ ساخت ویدیو شروع شد...\n\n"
        "🧠 سناریو آماده است\n"
        "🎨 در حال تولید تصاویر AI\n"
        "🎬 سپس تصاویر به ویدیو تبدیل می‌شوند.\n\n"
        "ممکن است چند دقیقه طول بکشد."
    )

    work_dir = BASE_DIR / f"user_{user_id}"

    work_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    image_files = []

    try:

        for i, scene in enumerate(project["scenes"], 1):

            await update.message.reply_text(
                f"🎨 تولید تصویر {i}/{SCENE_COUNT} ..."
            )

            prompt = (
                f"{scene['visual']}. "
                f"The subject is: {project['text']}. "
                "Vertical 9:16 composition, realistic photography, "
                "natural human proportions, coherent visual storytelling, "
                "high detail, professional cinematic lighting, "
                "no written text in the image."
            )

            image = await asyncio.to_thread(
                generate_image,
                prompt
            )

            image_file = work_dir / f"image_{i}.jpg"

            await asyncio.to_thread(
                prepare_image,
                image,
                scene["caption"],
                image_file
            )

            image_files.append(image_file)

        await update.message.reply_text(
            "🎬 تصاویر آماده شدند.\n"
            "در حال ساخت ویدیوی نهایی..."
        )

        output_file = work_dir / "final_video.mp4"

        audio_file = project.get("audio")

        await asyncio.to_thread(
            create_video,
            image_files,
            output_file,
            audio_file
        )

        if output_file.exists():

            await update.message.reply_video(
                video=output_file.open("rb"),
                caption=(
                    "🎬 ویدیوی شما آماده شد.\n\n"
                    "ساخته‌شده با AI"
                )
            )

        else:

            await update.message.reply_text(
                "❌ فایل ویدیو ساخته نشد."
            )

    except Exception as e:

        print("ERROR:", repr(e))

        await update.message.reply_text(
            "❌ هنگام ساخت ویدیو خطایی رخ داد.\n\n"
            f"{str(e)[:1000]}"
        )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is missing."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("clear", clear)
    )

    application.add_handler(
        CommandHandler("render", render)
    )

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    application.add_handler(
        MessageHandler(
            filters.AUDIO | filters.VOICE,
            handle_audio
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    print("🤖 AI Video Bot is running...")

    application.run_polling()


if __name__ == "__main__":
    main()
