import os
import io
import asyncio
import requests
import subprocess
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

from PIL import Image, ImageDraw, ImageFont


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

BASE_DIR = Path("video_work")
BASE_DIR.mkdir(exist_ok=True)

VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
SCENE_SECONDS = 5
SCENE_COUNT = 6

user_projects = {}
user_messages = {}


# =========================================================
# MESSAGE MEMORY
# =========================================================

def remember_message(user_id, message_id):

    if user_id not in user_messages:
        user_messages[user_id] = []

    user_messages[user_id].append(message_id)

    user_messages[user_id] = user_messages[user_id][-100:]


async def send_message(update, text, **kwargs):

    user_id = update.effective_user.id

    message = await update.effective_chat.send_message(
        text=text,
        **kwargs
    )

    remember_message(
        user_id,
        message.message_id
    )

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
# KEYBOARDS
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


def after_idea_keyboard():

    return InlineKeyboardMarkup([
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
    ])


# =========================================================
# IMAGE GENERATOR
# =========================================================

def generate_image(prompt):

    url = (
        "https://image.pollinations.ai/prompt/"
        + requests.utils.quote(prompt)
    )

    params = {
        "model": "flux",
        "width": VIDEO_WIDTH,
        "height": VIDEO_HEIGHT,
        "nologo": "true",
    }

    response = requests.get(
        url,
        params=params,
        timeout=180
    )

    response.raise_for_status()

    image = Image.open(
        io.BytesIO(response.content)
    ).convert("RGB")

    return image


# =========================================================
# CREATE SCENE IMAGE
# =========================================================

async def create_scene_image(
    prompt,
    output_path
):

    loop = asyncio.get_running_loop()

    image = await loop.run_in_executor(
        None,
        generate_image,
        prompt
    )

    image.save(
        output_path,
        "JPEG",
        quality=92
    )

    return output_path


# =========================================================
# FONT
# =========================================================

def get_font(size):

    possible_fonts = [

        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",

        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",

    ]

    for font_path in possible_fonts:

        if os.path.exists(font_path):

            try:

                return ImageFont.truetype(
                    font_path,
                    size
                )

            except Exception:
                pass

    return ImageFont.load_default()


# =========================================================
# ADD TEXT TO IMAGE
# =========================================================

def add_text_to_image(
    image,
    text
):

    image = image.copy()

    draw = ImageDraw.Draw(image)

    font = get_font(42)

    margin = 35

    max_width = VIDEO_WIDTH - (margin * 2)

    words = text.split()

    lines = []
    current = ""

    for word in words:

        test = (
            current + " " + word
        ).strip()

        bbox = draw.textbbox(
            (0, 0),
            test,
            font=font
        )

        if bbox[2] <= max_width:

            current = test

        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    if not lines:
        return image

    line_height = 55

    box_height = (
        len(lines) * line_height
        + 40
    )

    y = VIDEO_HEIGHT - box_height - 40

    draw.rounded_rectangle(
        (
            20,
            y,
            VIDEO_WIDTH - 20,
            VIDEO_HEIGHT - 20
        ),
        radius=25,
        fill=(0, 0, 0)
    )

    for line in lines:

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font
        )

        text_width = bbox[2] - bbox[0]

        x = (
            VIDEO_WIDTH
            - text_width
        ) // 2

        draw.text(
            (x, y + 20),
            line,
            font=font,
            fill=(255, 255, 255)
        )

        y += line_height

    return image


# =========================================================
# CREATE VIDEO
# =========================================================

def create_video_from_images(
    image_paths,
    output_path
):

    frames_dir = (
        output_path.parent
        / "frames"
    )

    frames_dir.mkdir(
        exist_ok=True
    )

    frame_paths = []

    for scene_index, image_path in enumerate(
        image_paths
    ):

        image = Image.open(
            image_path
        ).convert("RGB")

        image = image.resize(
            (
                VIDEO_WIDTH,
                VIDEO_HEIGHT
            )
        )

        # ---------------------------------------------
        # Create zoom effect
        # ---------------------------------------------

        frame_count = (
            SCENE_SECONDS * 24
        )

        for frame_number in range(
            frame_count
        ):

            progress = (
                frame_number
                / max(frame_count - 1, 1)
            )

            zoom = 1.0 + (
                progress * 0.08
            )

            crop_w = int(
                VIDEO_WIDTH / zoom
            )

            crop_h = int(
                VIDEO_HEIGHT / zoom
            )

            left = (
                VIDEO_WIDTH - crop_w
            ) // 2

            top = (
                VIDEO_HEIGHT - crop_h
            ) // 2

            frame = image.crop(
                (
                    left,
                    top,
                    left + crop_w,
                    top + crop_h
                )
            )

            frame = frame.resize(
                (
                    VIDEO_WIDTH,
                    VIDEO_HEIGHT
                ),
                Image.Resampling.LANCZOS
            )

            frame_file = (
                frames_dir
                / f"scene_{scene_index:02d}_"
                f"{frame_number:04d}.jpg"
            )

            frame.save(
                frame_file,
                "JPEG",
                quality=90
            )

            frame_paths.append(
                frame_file
            )

    concat_file = (
        output_path.parent
        / "frames.txt"
    )

    with open(
        concat_file,
        "w",
        encoding="utf-8"
    ) as f:

        for frame in frame_paths:

            f.write(
                f"file '{frame.resolve()}'\n"
            )

    command = [

        "ffmpeg",

        "-y",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        str(concat_file),

        "-vf",
        "fps=24",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-pix_fmt",
        "yuv420p",

        "-movflags",
        "+faststart",

        str(output_path)
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:

        raise RuntimeError(
            result.stderr[-3000:]
        )

    return output_path


# =========================================================
# BUILD VIDEO
# =========================================================

async def build_video(
    user_id,
    bot,
    chat_id
):

    project = user_projects.get(
        user_id
    )

    if not project:
        raise RuntimeError(
            "Project not found."
        )

    idea = project["idea"]

    project_dir = (
        BASE_DIR
        / str(user_id)
    )

    project_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    image_paths = []

    scenes = [

        f"""
        cinematic vertical video,
        realistic professional photography,
        opening scene about:
        {idea},
        natural lighting,
        highly detailed,
        realistic,
        professional advertising style
        """,

        f"""
        cinematic vertical scene,
        realistic farmers and agriculture,
        showing the main subject:
        {idea},
        professional commercial photography,
        natural environment,
        highly detailed
        """,

        f"""
        close-up cinematic scene,
        realistic details,
        showing an important aspect of:
        {idea},
        professional advertising,
        natural colors,
        photorealistic
        """,

        f"""
        realistic agricultural scene,
        practical real-world example of:
        {idea},
        cinematic composition,
        professional commercial video,
        highly detailed
        """,

        f"""
        beautiful cinematic scene,
        successful result related to:
        {idea},
        realistic agriculture,
        professional advertising photography,
        natural lighting
        """,

        f"""
        final cinematic advertising scene about:
        {idea},
        optimistic ending,
        beautiful realistic agricultural environment,
        professional commercial photography,
        highly detailed
        """
    ]

    for index, scene_prompt in enumerate(
        scenes,
        start=1
    ):

        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🖼 ساخت تصویر "
                f"{index}/{SCENE_COUNT}..."
            )
        )

        output_path = (
            project_dir
            / f"scene_{index}.jpg"
        )

        await create_scene_image(
            scene_prompt,
            output_path
        )

        image_paths.append(
            output_path
        )

    await bot.send_message(
        chat_id=chat_id,
        text="🎞 تصاویر آماده شدند.\nدر حال ساخت ویدیو..."
    )

    video_path = (
        project_dir
        / "final_video.mp4"
    )

    loop = asyncio.get_running_loop()

    await loop.run_in_executor(
        None,
        create_video_from_images,
        image_paths,
        video_path
    )

    return video_path


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    chat_id = update.effective_chat.id

    user_projects.pop(
        user_id,
        None
    )

    await delete_old_messages(
        context.bot,
        chat_id,
        user_id
    )

    message = await update.effective_chat.send_message(
        text=(
            "🎬 سلام!\n\n"
            "به ربات ساخت ویدیو خوش آمدی.\n\n"
            "برای شروع روی دکمه زیر بزن:"
        ),
        reply_markup=main_keyboard()
    )

    remember_message(
        user_id,
        message.message_id
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    # =====================================================
    # START VIDEO
    # =====================================================

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
                "مثلاً:\n\n"
                "یک تبلیغ حرفه‌ای برای کود "
                "گیاهی ارگانیک بساز."
            )
        )

        return

    # =====================================================
    # CLEAR
    # =====================================================

    if query.data == "clear_project":

        user_projects.pop(
            user_id,
            None
        )

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

    # =====================================================
    # MAKE VIDEO
    # =====================================================

    if query.data == "make_video":

        project = user_projects.get(
            user_id
        )

        if not project:

            await query.edit_message_text(
                text=(
                    "⚠️ پروژه‌ای وجود ندارد.\n\n"
                    "ابتدا روی شروع ساخت ویدیو بزن."
                ),
                reply_markup=main_keyboard()
            )

            return

        if not project.get("idea"):

            await query.edit_message_text(
                text=(
                    "⚠️ هنوز ایده‌ای دریافت نکرده‌ام."
                ),
                reply_markup=main_keyboard()
            )

            return

        await query.edit_message_text(
            text=(
                "🚀 شروع ساخت ویدیو...\n\n"
                "لطفاً صبر کن."
            )
        )

        try:

            video_path = await build_video(
                user_id,
                context.bot,
                query.message.chat_id
            )

            with open(
                video_path,
                "rb"
            ) as video_file:

                sent = await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=video_file,
                    caption=(
                        "🎉 ویدیوی شما آماده شد!"
                    ),
                    supports_streaming=True
                )

            remember_message(
                user_id,
                sent.message_id
            )

        except Exception as error:

            print(
                "VIDEO ERROR:",
                repr(error)
            )

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    "❌ هنگام ساخت ویدیو خطایی رخ داد.\n\n"
                    f"جزئیات:\n{str(error)[:1500]}"
                )
            )

        return


# =========================================================
# TEXT HANDLER
# =========================================================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    remember_message(
        user_id,
        update.message.message_id
    )

    text = update.message.text.strip()

    if not text:
        return

    if user_id not in user_projects:

        await send_message(
            update,
            "لطفاً ابتدا /start را بزن."
        )

        return

    project = user_projects[user_id]

    # =====================================================
    # RECEIVE IDEA
    # =====================================================

    if project.get("status") == "waiting_for_idea":

        project["idea"] = text

        project["status"] = "idea_received"

        project["storyboard"] = [

            {
                "scene": 1,
                "description":
                    f"شروع ویدیو درباره {text}"
            },

            {
                "scene": 2,
                "description":
                    f"معرفی موضوع {text}"
            },

            {
                "scene": 3,
                "description":
                    f"توضیح اصلی درباره {text}"
            },

            {
                "scene": 4,
                "description":
                    f"مثال واقعی درباره {text}"
            },

            {
                "scene": 5,
                "description":
                    f"نتیجه و مزایای {text}"
            },

            {
                "scene": 6,
                "description":
                    f"جمع‌بندی {text}"
            }
        ]

        await send_message(
            update,
            (
                "✅ ایده دریافت شد!\n\n"
                f"💡 {text}\n\n"
                "📋 سناریوی اولیه آماده شد.\n\n"
                "۶ صحنه برای ویدیو در نظر گرفته شده است.\n\n"
                "اگر آماده‌ای، روی دکمه زیر بزن:"
            ),
            reply_markup=after_idea_keyboard()
        )

        return

    # =====================================================
    # NEW IDEA
    # =====================================================

    if project.get("status") == "idea_received":

        project["idea"] = text

        await send_message(
            update,
            (
                "✅ ایده جدید ثبت شد.\n\n"
                f"💡 {text}\n\n"
                "برای ساخت ویدیو روی دکمه زیر بزن."
            ),
            reply_markup=after_idea_keyboard()
        )

        return

    await send_message(
        update,
        (
            "پیامت دریافت شد ✅\n\n"
            "برای شروع پروژه جدید /start را بزن."
        ),
        reply_markup=main_keyboard()
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context
):

    print("====================================")
    print("BOT ERROR")
    print("====================================")
    print(repr(context.error))
    print("====================================")


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        print(
            "ERROR: BOT_TOKEN is not set."
        )

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

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    application.add_error_handler(
        error_handler
    )

    print(
        "Bot is running..."
    )

    print(
        "Waiting for Telegram messages..."
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()
