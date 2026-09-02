import os
import re
import asyncio
import tempfile
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# تنظیمات
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

WIDTH = 720
HEIGHT = 1280
FPS = 15

SCENE_COUNT = 6
SCENE_DURATION = 5

drafts = {}


# =========================================================
# فونت
# =========================================================

def get_font(size):
    fonts = [
        r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        r"/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        r"/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]

    for font in fonts:
        if os.path.exists(font):
            return ImageFont.truetype(font, size)

    return ImageFont.load_default()


# =========================================================
# فارسی
# =========================================================

def rtl(text):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(
            arabic_reshaper.reshape(text)
        )

    except Exception:
        return text


# =========================================================
# تشخیص نوع پروژه
# =========================================================

def detect_type(text):

    t = text.lower()

    advertising_words = [
        "تبلیغ",
        "فروش",
        "خرید",
        "محصول",
        "قیمت",
        "مشتری",
        "برند",
        "تبلیغاتی",
        "اینستاگرام",
        "فروشگاه",
    ]

    education_words = [
        "آموزش",
        "آموزشی",
        "یاد بگیریم",
        "یادگیری",
        "چگونه",
        "چطور",
        "درس",
        "نکته",
        "آموزش دهید",
    ]

    product_words = [
        "محصول",
        "کالا",
        "معرفی",
        "معرفی محصول",
    ]

    if any(x in t for x in education_words):
        return "education"

    if any(x in t for x in advertising_words):
        return "advertising"

    if any(x in t for x in product_words):
        return "product"

    return "general"


# =========================================================
# استخراج موضوع اصلی
# =========================================================

def clean_subject(text):

    text = re.sub(
        r"(یک|یه|برای|بساز|ساخت|ایجاد|کن|مناسب|جذاب|حرفه‌ای|حرفه ای)",
        " ",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    if len(text) > 120:
        text = text[:120] + "..."

    return text


# =========================================================
# ساخت سناریو
# =========================================================

def create_story(text):

    project_type = detect_type(text)
    subject = clean_subject(text)

    if project_type == "education":

        scenes = [
            (
                "شروع",
                "امروز یک نکته مهم را یاد می‌گیریم",
                subject
            ),
            (
                "مسئله",
                "چرا این موضوع اهمیت دارد؟",
                subject
            ),
            (
                "آموزش",
                "قدم اول را با دقت انجام دهید",
                subject
            ),
            (
                "نکته مهم",
                "این نکته می‌تواند نتیجه را بهتر کند",
                subject
            ),
            (
                "جمع‌بندی",
                "حالا می‌دانید چگونه بهتر عمل کنید",
                subject
            ),
            (
                "پایان",
                "این آموزش را ذخیره و با دیگران به اشتراک بگذارید",
                subject
            ),
        ]

    elif project_type == "product":

        scenes = [
            (
                "معرفی",
                "با این محصول بیشتر آشنا شوید",
                subject
            ),
            (
                "نیاز",
                "اگر به دنبال یک انتخاب بهتر هستید...",
                subject
            ),
            (
                "محصول",
                "راه‌حلی ساده و کاربردی",
                subject
            ),
            (
                "مزیت",
                "طراحی شده برای استفاده آسان و نتیجه بهتر",
                subject
            ),
            (
                "نتیجه",
                "انتخاب مناسب می‌تواند تفاوت ایجاد کند",
                subject
            ),
            (
                "اقدام",
                "برای اطلاعات بیشتر با ما تماس بگیرید",
                subject
            ),
        ]

    elif project_type == "advertising":

        scenes = [
            (
                "جذب مخاطب",
                "دنبال یک انتخاب بهتر هستید؟",
                subject
            ),
            (
                "مشکل",
                "وقت آن رسیده راه‌حل بهتری پیدا کنید",
                subject
            ),
            (
                "راه‌حل",
                "یک انتخاب حرفه‌ای برای شما",
                subject
            ),
            (
                "مزیت",
                "کیفیت، کاربرد و تجربه بهتر",
                subject
            ),
            (
                "پیشنهاد",
                "این فرصت را از دست ندهید",
                subject
            ),
            (
                "اقدام",
                "همین امروز اطلاعات بیشتری دریافت کنید",
                subject
            ),
        ]

    else:

        scenes = [
            (
                "شروع",
                "یک ایده جالب برای شما",
                subject
            ),
            (
                "موضوع",
                "بیایید موضوع را بهتر بشناسیم",
                subject
            ),
            (
                "نکته اول",
                "این بخش اهمیت زیادی دارد",
                subject
            ),
            (
                "نکته دوم",
                "با یک روش ساده می‌توان بهتر عمل کرد",
                subject
            ),
            (
                "نتیجه",
                "حالا تصویر کامل‌تری دارید",
                subject
            ),
            (
                "پایان",
                "برای مطالب بیشتر همراه ما باشید",
                subject
            ),
        ]

    return project_type, scenes


# =========================================================
# نمایش سناریو
# =========================================================

def story_to_text(project_type, scenes):

    names = {
        "advertising": "📢 تبلیغاتی",
        "education": "🎓 آموزشی",
        "product": "🛍 معرفی محصول",
        "general": "🎬 عمومی",
    }

    result = [
        "🎬 سناریوی پیشنهادی",
        "",
        f"نوع محتوا: {names.get(project_type, '🎬 عمومی')}",
        "",
    ]

    for i, (title, main, subject) in enumerate(scenes, 1):

        result.append(
            f"🎞 صحنه {i} — {title}"
        )

        result.append(
            f"📝 {main}"
        )

        result.append(
            f"🎯 موضوع: {subject}"
        )

        result.append("")

    result.append(
        "اگر سناریو مورد تأیید است، /render را بزن."
    )

    return "\n".join(result)


# =========================================================
# شکستن متن برای نمایش
# =========================================================

def wrap_text(draw, text, font, max_width):

    words = text.split()

    lines = []
    current = ""

    for word in words:

        test = (
            word
            if not current
            else current + " " + word
        )

        bbox = draw.textbbox(
            (0, 0),
            rtl(test),
            font=font
        )

        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


# =========================================================
# ساخت تصویر صحنه
# =========================================================

def create_scene(
    title,
    main_text,
    subject,
    index,
    output,
    photo=None
):

    backgrounds = [
        (18, 30, 48),
        (24, 40, 58),
        (20, 48, 42),
        (48, 36, 25),
        (38, 28, 52),
        (18, 42, 52),
    ]

    img = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        backgrounds[index]
    )

    # -----------------------------------------------------
    # اگر عکس محصول وجود دارد
    # -----------------------------------------------------

    if photo and os.path.exists(photo):

        try:

            source = Image.open(photo).convert("RGB")

            scale = max(
                WIDTH / source.width,
                HEIGHT / source.height
            )

            new_size = (
                int(source.width * scale),
                int(source.height * scale)
            )

            source = source.resize(
                new_size,
                Image.Resampling.LANCZOS
            )

            left = (
                source.width - WIDTH
            ) // 2

            top = (
                source.height - HEIGHT
            ) // 2

            source = source.crop(
                (
                    left,
                    top,
                    left + WIDTH,
                    top + HEIGHT
                )
            )

            img.paste(source)

            overlay = Image.new(
                "RGBA",
                (WIDTH, HEIGHT),
                (0, 0, 0, 110)
            )

            img = Image.alpha_composite(
                img.convert("RGBA"),
                overlay
            ).convert("RGB")

        except Exception:
            pass

    draw = ImageDraw.Draw(img)

    # -----------------------------------------------------
    # تزئین
    # -----------------------------------------------------

    draw.ellipse(
        (-180, -150, 300, 330),
        fill=(50, 80, 105)
    )

    draw.ellipse(
        (
            WIDTH - 300,
            HEIGHT - 300,
            WIDTH + 180,
            HEIGHT + 180
        ),
        fill=(75, 55, 90)
    )

    # -----------------------------------------------------
    # عنوان
    # -----------------------------------------------------

    title_font = get_font(38)

    draw.text(
        (WIDTH // 2, 160),
        rtl(title),
        font=title_font,
        anchor="mm",
        fill="white"
    )

    # -----------------------------------------------------
    # متن اصلی
    # -----------------------------------------------------

    main_font = get_font(56)

    lines = wrap_text(
        draw,
        main_text,
        main_font,
        WIDTH - 100
    )

    lines = lines[:5]

    total_height = len(lines) * 90

    y = (
        HEIGHT // 2
        - total_height // 2
    )

    for line in lines:

        draw.text(
            (WIDTH // 2, y),
            rtl(line),
            font=main_font,
            anchor="mm",
            fill="white",
            stroke_width=2,
            stroke_fill=(0, 0, 0)
        )

        y += 90

    # -----------------------------------------------------
    # موضوع
    # -----------------------------------------------------

    subject_font = get_font(28)

    subject_lines = wrap_text(
        draw,
        subject,
        subject_font,
        WIDTH - 120
    )

    subject_lines = subject_lines[:2]

    y = HEIGHT - 220

    for line in subject_lines:

        draw.text(
            (WIDTH // 2, y),
            rtl(line),
            font=subject_font,
            anchor="mm",
            fill=(235, 235, 235)
        )

        y += 42

    # -----------------------------------------------------
    # شماره صحنه
    # -----------------------------------------------------

    scene_font = get_font(25)

    draw.text(
        (WIDTH // 2, HEIGHT - 70),
        rtl(f"صحنه {index + 1} از 6"),
        font=scene_font,
        anchor="mm",
        fill=(210, 210, 210)
    )

    img.save(
        output,
        quality=95
    )


# =========================================================
# FFmpeg
# =========================================================

def run_ffmpeg(command):

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-4000:]
        )


# =========================================================
# ساخت ویدئو
# =========================================================

def create_video(
    scenes,
    photo=None,
    audio=None
):

    workdir = Path(
        tempfile.mkdtemp(
            prefix="ai_video_"
        )
    )

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    parts = []

    for i, (title, main_text, subject) in enumerate(scenes):

        image_path = (
            workdir / f"scene_{i}.jpg"
        )

        video_path = (
            workdir / f"scene_{i}.mp4"
        )

        create_scene(
            title,
            main_text,
            subject,
            i,
            str(image_path),
            photo
        )

        command = [
            ffmpeg,
            "-y",

            "-loop",
            "1",

            "-i",
            str(image_path),

            "-t",
            str(SCENE_DURATION),

            "-vf",

            (
                "zoompan="
                "z='min(zoom+0.0015,1.12)':"
                "d=75:"
                f"s={WIDTH}x{HEIGHT}:"
                f"fps={FPS},"
                "fade=t=in:st=0:d=0.3,"
                "fade=t=out:st=4.7:d=0.3"
            ),

            "-an",

            "-c:v",
            "libx264",

            "-pix_fmt",
            "yuv420p",

            "-movflags",
            "+faststart",

            str(video_path)
        ]

        run_ffmpeg(command)

        parts.append(video_path)

    # -----------------------------------------------------
    # اتصال صحنه‌ها
    # -----------------------------------------------------

    list_file = (
        workdir / "list.txt"
    )

    with open(
        list_file,
        "w",
        encoding="utf-8"
    ) as f:

        for part in parts:

            f.write(
                f"file '{part.as_posix()}'\n"
            )

    joined = (
        workdir / "joined.mp4"
    )

    run_ffmpeg([
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(joined)
    ])

    # -----------------------------------------------------
    # افزودن صدا
    # -----------------------------------------------------

    if audio and os.path.exists(audio):

        final = (
            workdir / "final.mp4"
        )

        run_ffmpeg([
            ffmpeg,
            "-y",

            "-i",
            str(joined),

            "-i",
            str(audio),

            "-filter_complex",
            "[1:a]apad,atrim=0:30[a]",

            "-map",
            "0:v",

            "-map",
            "[a]",

            "-c:v",
            "copy",

            "-c:a",
            "aac",

            "-shortest",

            str(final)
        ])

        return str(final)

    return str(joined)


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = """
🎬 ربات ساخت ویدئو آماده است!

من می‌توانم برایت ویدئوهای:

📢 تبلیغاتی
🛍 معرفی محصول
🎓 آموزشی
📱 اینستاگرامی

بسازم.

روش کار:

1️⃣ متن یا ایده را بفرست
2️⃣ اگر عکس محصول داری، عکس را بفرست
3️⃣ اگر گویندگی داری، MP3 یا Voice بفرست
4️⃣ من سناریو را می‌سازم
5️⃣ اگر تأیید کردی /render را بزن

دستورها:

/render
ساخت ویدئو

/clear
پاک کردن پروژه فعلی
"""

    await update.message.reply_text(
        message
    )


# =========================================================
# دریافت متن
# =========================================================

async def receive_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    text = update.message.text.strip()

    project_type, scenes = create_story(text)

    drafts[chat_id] = {
        "text": text,
        "type": project_type,
        "scenes": scenes,
    }

    story = story_to_text(
        project_type,
        scenes
    )

    await update.message.reply_text(
        story
    )


# =========================================================
# دریافت عکس
# =========================================================

async def receive_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    if chat_id not in drafts:
        drafts[chat_id] = {}

    photo = update.message.photo[-1]

    file = await context.bot.get_file(
        photo.file_id
    )

    workdir = Path(
        tempfile.mkdtemp(
            prefix="product_photo_"
        )
    )

    path = (
        workdir / "product.jpg"
    )

    await file.download_to_drive(
        str(path)
    )

    drafts[chat_id]["photo"] = str(path)

    if update.message.caption:

        text = update.message.caption.strip()

        project_type, scenes = create_story(
            text
        )

        drafts[chat_id]["text"] = text
        drafts[chat_id]["type"] = project_type
        drafts[chat_id]["scenes"] = scenes

        story = story_to_text(
            project_type,
            scenes
        )

        await update.message.reply_text(
            "🖼️ عکس دریافت شد.\n\n"
            + story
        )

    else:

        await update.message.reply_text(
            "🖼️ عکس محصول دریافت شد.\n"
            "حالا متن را بفرست."
        )


# =========================================================
# دریافت صدا
# =========================================================

async def receive_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    if chat_id not in drafts:
        drafts[chat_id] = {}

    if update.message.audio:

        file_id = (
            update.message.audio.file_id
        )

        extension = ".mp3"

    else:

        file_id = (
            update.message.voice.file_id
        )

        extension = ".ogg"

    file = await context.bot.get_file(
        file_id
    )

    workdir = Path(
        tempfile.mkdtemp(
            prefix="voice_"
        )
    )

    path = (
        workdir / f"voice{extension}"
    )

    await file.download_to_drive(
        str(path)
    )

    drafts[chat_id]["audio"] = str(path)

    await update.message.reply_text(
        "🔊 گویندگی دریافت شد.\n"
        "اگر سناریو را تأیید کرده‌ای، /render را بزن."
    )


# =========================================================
# /clear
# =========================================================

async def clear(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    drafts.pop(
        update.effective_chat.id,
        None
    )

    await update.message.reply_text(
        "🗑 پروژه فعلی پاک شد."
    )


# =========================================================
# /render
# =========================================================

async def render(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    draft = drafts.get(chat_id)

    if not draft or not draft.get("scenes"):

        await update.message.reply_text(
            "❌ هنوز سناریویی نداریم.\n"
            "اول متن یا ایده را بفرست."
        )

        return

    await update.message.reply_text(
        "🎬 سناریو تأیید شد.\n\n"
        "در حال ساخت ویدئو هستم...\n"
        "⏳ لطفاً صبر کن."
    )

    try:

        video = await asyncio.to_thread(
            create_video,
            draft["scenes"],
            draft.get("photo"),
            draft.get("audio")
        )

        with open(
            video,
            "rb"
        ) as f:

            await update.message.reply_video(
                video=f,
                caption=(
                    "🎬 ویدئو آماده شد!\n\n"
                    "نسخه فعلی: موشن‌گرافیک"
                ),
                supports_streaming=True
            )

        drafts.pop(
            chat_id,
            None
        )

    except Exception as e:

        await update.message.reply_text(
            "❌ خطا هنگام ساخت ویدئو:\n\n"
            + str(e)[-3000:]
        )


# =========================================================
# اجرای ربات
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN تنظیم نشده است."
        )

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "clear",
            clear
        )
    )

    app.add_handler(
        CommandHandler(
            "render",
            render
        )
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            receive_photo
        )
    )

    app.add_handler(
        MessageHandler(
            filters.AUDIO | filters.VOICE,
            receive_audio
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_text
        )
    )

    print(
        "AI Video Telegram Bot is running..."
    )

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
