import os
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

# =========================
# تنظیمات
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

WIDTH = 720
HEIGHT = 1280
FPS = 15
SCENE_DURATION = 5
SCENE_COUNT = 6

# ذخیره موقت اطلاعات هر کاربر
drafts = {}


# =========================
# فونت فارسی
# =========================

def get_font(size):
    fonts = [
        r"C:\Windows\Fonts\tahoma.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ]

    for font in fonts:
        if os.path.exists(font):
            return ImageFont.truetype(font, size)

    return ImageFont.load_default()


# =========================
# متن فارسی
# =========================

def rtl_text(text):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)

    except Exception:
        return text


# =========================
# شکستن متن
# =========================

def split_text(text, count=6):
    text = text.strip()

    if not text:
        return [""] * count

    # ابتدا بر اساس جمله‌ها
    parts = []

    for separator in ["؟", "!", "！", ".", "،", "\n"]:
        if separator in text:
            temp = []

            for p in text.split(separator):
                p = p.strip()
                if p:
                    temp.append(p)

            if len(temp) >= 2:
                parts = temp
                break

    if not parts:
        words = text.split()
        chunk = max(1, len(words) // count)

        for i in range(0, len(words), chunk):
            parts.append(" ".join(words[i:i + chunk]))

    # دقیقاً count بخش
    if len(parts) > count:
        parts = parts[:count]

    while len(parts) < count:
        parts.append("")

    return parts


# =========================
# ساخت تصویر صحنه
# =========================

def create_scene(text, index, output, photo=None):

    img = Image.new("RGB", (WIDTH, HEIGHT), (20, 20, 25))
    draw = ImageDraw.Draw(img)

    # رنگ‌های مختلف برای صحنه‌ها
    backgrounds = [
        (18, 25, 40),
        (25, 35, 55),
        (20, 45, 40),
        (45, 35, 25),
        (35, 25, 50),
        (15, 35, 45),
    ]

    if photo and os.path.exists(photo):

        try:
            source = Image.open(photo).convert("RGB")

            # نسبت تصویر
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

            left = (source.width - WIDTH) // 2
            top = (source.height - HEIGHT) // 2

            source = source.crop(
                (left, top, left + WIDTH, top + HEIGHT)
            )

            img.paste(source)

            # لایه تاریک برای خوانایی متن
            overlay = Image.new(
                "RGBA",
                (WIDTH, HEIGHT),
                (0, 0, 0, 90)
            )

            img = Image.alpha_composite(
                img.convert("RGBA"),
                overlay
            ).convert("RGB")

            draw = ImageDraw.Draw(img)

        except Exception:
            img = Image.new(
                "RGB",
                (WIDTH, HEIGHT),
                backgrounds[index]
            )
            draw = ImageDraw.Draw(img)

    else:
        # پس‌زمینه ساده زیبا
        img = Image.new(
            "RGB",
            (WIDTH, HEIGHT),
            backgrounds[index]
        )

        draw = ImageDraw.Draw(img)

        # اشکال تزئینی
        draw.ellipse(
            (-180, -180, 350, 350),
            fill=(40, 70, 100)
        )

        draw.ellipse(
            (WIDTH - 350, HEIGHT - 350,
             WIDTH + 150, HEIGHT + 150),
            fill=(70, 50, 80)
        )

    # شماره صحنه
    small_font = get_font(34)

    scene_label = rtl_text(
        f"صحنه {index + 1}"
    )

    draw.text(
        (WIDTH // 2, 170),
        scene_label,
        font=small_font,
        anchor="mm",
        fill="white"
    )

    # متن اصلی
    font = get_font(55)

    # شکست خطوط
    words = text.split()
    lines = []
    current = ""

    for word in words:

        test = current + " " + word

        bbox = draw.textbbox(
            (0, 0),
            rtl_text(test),
            font=font
        )

        if bbox[2] - bbox[0] < WIDTH - 100:
            current = test.strip()

        else:
            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    # حداکثر 5 خط
    lines = lines[:5]

    y = HEIGHT // 2 - (len(lines) * 40)

    for line in lines:

        shaped = rtl_text(line)

        draw.text(
            (WIDTH // 2, y),
            shaped,
            font=font,
            anchor="mm",
            fill="white",
            stroke_width=2,
            stroke_fill=(0, 0, 0)
        )

        y += 85

    # پایین تصویر
    footer_font = get_font(30)

    footer = rtl_text(
        "ساخته شده با ربات ویدئوساز"
    )

    draw.text(
        (WIDTH // 2, HEIGHT - 100),
        footer,
        font=footer_font,
        anchor="mm",
        fill=(220, 220, 220)
    )

    img.save(output, quality=95)


# =========================
# اجرای FFmpeg
# =========================

def run_ffmpeg(command):

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:])


# =========================
# ساخت ویدئو
# =========================

def create_video(text, photo=None, audio=None):

    workdir = Path(
        tempfile.mkdtemp(prefix="telegram_video_")
    )

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    scenes = split_text(text, SCENE_COUNT)

    video_parts = []

    for i, scene_text in enumerate(scenes):

        image_path = workdir / f"scene_{i}.jpg"
        video_path = workdir / f"part_{i}.mp4"

        create_scene(
            scene_text,
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

        video_parts.append(video_path)

    # فایل لیست
    list_file = workdir / "list.txt"

    with open(list_file, "w", encoding="utf-8") as f:

        for part in video_parts:
            f.write(
                f"file '{part.as_posix()}'\n"
            )

    joined = workdir / "joined.mp4"

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

    final = workdir / "final.mp4"

    if audio and os.path.exists(audio):

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

    else:
        final = joined

    return str(final)


# =========================
# Telegram
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
🎬 ربات ویدئوساز آماده است!

برای ساخت ویدئو:

1️⃣ متن تبلیغ یا آموزش را بفرست
2️⃣ اگر عکس محصول داری، عکس را هم بفرست
3️⃣ اگر گویندگی داری، فایل MP3 یا Voice را بفرست
4️⃣ در پایان /render را بزن

مثال:

«یک تبلیغ جذاب برای کود طبیعی کشاورزی
که باعث رشد بهتر گیاه می‌شود.»

دستورها:

/render  ساخت ویدئو
/clear   پاک کردن پروژه فعلی
"""

    await update.message.reply_text(text)


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):

    drafts.pop(update.effective_chat.id, None)

    await update.message.reply_text(
        "🗑️ پروژه فعلی پاک شد."
    )


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if chat_id not in drafts:
        drafts[chat_id] = {}

    drafts[chat_id]["text"] = update.message.text

    await update.message.reply_text(
        "✅ متن دریافت شد.\n\n"
        "اگر عکس محصول داری بفرست.\n"
        "اگر گویندگی داری MP3 یا Voice بفرست.\n"
        "بعد /render را بزن."
    )


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if chat_id not in drafts:
        drafts[chat_id] = {}

    photo = update.message.photo[-1]

    file = await context.bot.get_file(
        photo.file_id
    )

    workdir = Path(
        tempfile.mkdtemp(prefix="photo_")
    )

    path = workdir / "product.jpg"

    await file.download_to_drive(str(path))

    drafts[chat_id]["photo"] = str(path)

    if update.message.caption:
        drafts[chat_id]["text"] = update.message.caption

    await update.message.reply_text(
        "🖼️ عکس دریافت شد.\n"
        "حالا متن را بفرست یا /render را بزن."
    )


async def receive_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if chat_id not in drafts:
        drafts[chat_id] = {}

    if update.message.audio:
        file_id = update.message.audio.file_id
        extension = ".mp3"

    else:
        file_id = update.message.voice.file_id
        extension = ".ogg"

    file = await context.bot.get_file(file_id)

    workdir = Path(
        tempfile.mkdtemp(prefix="audio_")
    )

    path = workdir / f"voice{extension}"

    await file.download_to_drive(str(path))

    drafts[chat_id]["audio"] = str(path)

    await update.message.reply_text(
        "🔊 فایل صوتی دریافت شد.\n"
        "حالا /render را بزن."
    )


async def render(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    draft = drafts.get(chat_id)

    if not draft or not draft.get("text"):

        await update.message.reply_text(
            "❌ هنوز متنی برای ساخت ویدئو دریافت نکرده‌ام."
        )

        return

    await update.message.reply_text(
        "🎬 در حال ساخت ویدئو هستم...\n"
        "ممکن است چند دقیقه طول بکشد."
    )

    try:

        video = await asyncio.to_thread(
            create_video,
            draft["text"],
            draft.get("photo"),
            draft.get("audio")
        )

        with open(video, "rb") as f:

            await update.message.reply_video(
                video=f,
                caption="🎬 ویدئوی شما آماده شد.",
                supports_streaming=True
            )

        drafts.pop(chat_id, None)

    except Exception as e:

        await update.message.reply_text(
            "❌ خطا در ساخت ویدئو:\n\n"
            + str(e)[-2500:]
        )


# =========================
# Main
# =========================

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
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("clear", clear)
    )

    app.add_handler(
        CommandHandler("render", render)
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

    print("Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
