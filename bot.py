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

from PIL import Image


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

BASE_DIR = Path("video_work")
BASE_DIR.mkdir(exist_ok=True)

VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280

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


async def delete_old_messages(
    bot,
    chat_id,
    user_id
):

    messages = user_messages.get(
        user_id,
        []
    )

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
# MAIN KEYBOARD
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
# IDEA KEYBOARD
# =========================================================

def idea_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "⏱ انتخاب مدت",
                callback_data="choose_duration"
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
# DURATION KEYBOARD
# =========================================================

def duration_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "15 ثانیه",
                callback_data="duration_15"
            ),
            InlineKeyboardButton(
                "30 ثانیه",
                callback_data="duration_30"
            )
        ],

        [
            InlineKeyboardButton(
                "45 ثانیه",
                callback_data="duration_45"
            ),
            InlineKeyboardButton(
                "60 ثانیه",
                callback_data="duration_60"
            )
        ],

        [
            InlineKeyboardButton(
                "✏️ مدت دلخواه",
                callback_data="duration_custom"
            )
        ]

    ])


# =========================================================
# IMAGE COUNT KEYBOARD
# =========================================================

def image_count_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "3 تصویر",
                callback_data="images_3"
            ),

            InlineKeyboardButton(
                "6 تصویر",
                callback_data="images_6"
            )
        ],

        [
            InlineKeyboardButton(
                "9 تصویر",
                callback_data="images_9"
            ),

            InlineKeyboardButton(
                "12 تصویر",
                callback_data="images_12"
            )
        ],

        [
            InlineKeyboardButton(
                "✏️ تعداد دلخواه",
                callback_data="images_custom"
            )
        ]

    ])


# =========================================================
# BUILD KEYBOARD
# =========================================================

def build_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "🎬 ساخت ویدیو",
                callback_data="make_video"
            )
        ],

        [
            InlineKeyboardButton(
                "🔄 تغییر تنظیمات",
                callback_data="choose_duration"
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

    return Image.open(
        io.BytesIO(
            response.content
        )
    ).convert("RGB")


# =========================================================
# CREATE IMAGE
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
# CREATE PROMPTS
# =========================================================

def create_scene_prompts(
    idea,
    count
):

    # -----------------------------------------------------
    # سناریوی پایه
    # -----------------------------------------------------

    templates = [

        "opening establishing shot introducing the subject",

        "show the main problem or situation related to the subject",

        "show the product, solution or main action",

        "show how the solution is being used in real life",

        "show a close-up detailed result",

        "show improvement and positive results",

        "show a wider successful real-world situation",

        "show a satisfied person experiencing the result",

        "strong cinematic conclusion related to the subject",

        "professional advertising ending",

        "final impressive result",

        "clean memorable closing shot"

    ]

    prompts = []

    for i in range(count):

        template = templates[
            i % len(templates)
        ]

        prompt = f"""
Create scene {i + 1} of {count} for ONE continuous
professional commercial video.

MAIN SUBJECT:
{idea}

SCENE PURPOSE:
{template}

IMPORTANT:
The image must clearly represent the MAIN SUBJECT.
Do not create an unrelated generic image.

Keep the same visual world throughout the entire video:
same location style,
same season,
same realistic photographic style,
same type of people,
same product identity if a product exists,
same general lighting,
same color mood,
same environment.

The scene must logically continue from the previous
and lead naturally to the next scene.

Style:
photorealistic,
cinematic commercial photography,
professional advertising,
realistic details,
natural lighting,
vertical 9:16 composition,
no text,
no logo,
no watermark.

The main subject must be visually obvious.
"""

        prompts.append(
            prompt
        )

    return prompts


# =========================================================
# CREATE VIDEO
# =========================================================

def create_video_from_images(
    image_paths,
    output_path,
    total_seconds
):

    count = len(image_paths)

    seconds_per_image = (
        total_seconds / count
    )

    fps = 24

    frames_per_image = int(
        seconds_per_image * fps
    )

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

        for frame_number in range(
            frames_per_image
        ):

            progress = (
                frame_number
                / max(
                    frames_per_image - 1,
                    1
                )
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
                / (
                    f"scene_{scene_index:02d}_"
                    f"{frame_number:05d}.jpg"
                )
            )

            frame.save(
                frame_file,
                "JPEG",
                quality=88
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

    project = user_projects[user_id]

    idea = project["idea"]

    duration = project["duration"]

    image_count = project["image_count"]

    project_dir = (
        BASE_DIR
        / str(user_id)
    )

    project_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    prompts = create_scene_prompts(
        idea,
        image_count
    )

    image_paths = []

    # -----------------------------------------------------
    # Generate images
    # -----------------------------------------------------

    for index, prompt in enumerate(
        prompts,
        start=1
    ):

        status_message = await bot.send_message(

            chat_id=chat_id,

            text=(
                f"🖼 ساخت تصویر "
                f"{index}/{image_count}\n\n"
                f"⏱ مدت ویدیو: {duration} ثانیه\n"
                f"📌 موضوع:\n{idea[:300]}"
            )

        )

        try:

            image_path = (
                project_dir
                / f"scene_{index}.jpg"
            )

            await create_scene_image(
                prompt,
                image_path
            )

            image_paths.append(
                image_path
            )

            try:

                await status_message.edit_text(
                    (
                        f"✅ تصویر "
                        f"{index}/{image_count} آماده شد."
                    )
                )

            except Exception:
                pass

        except Exception as error:

            raise RuntimeError(
                f"خطا در ساخت تصویر {index}:\n"
                f"{str(error)}"
            )

    # -----------------------------------------------------
    # Create video
    # -----------------------------------------------------

    await bot.send_message(
        chat_id=chat_id,
        text=(
            "🎞 همه تصاویر آماده شدند.\n\n"
            "در حال ساخت ویدیو..."
        )
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

        video_path,

        duration

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

            "duration": None,

            "image_count": None,

            "status": "waiting_for_idea"

        }

        await query.edit_message_text(

            text=(
                "🎬 ساخت ویدیو\n\n"
                "اول ایده و موضوع ویدیوت را بنویس.\n\n"
                "مثلاً:\n\n"
                "یک تبلیغ حرفه‌ای برای کود "
                "گیاهی ارگانیک در مزرعه گندم."
            )

        )

        return

    # =====================================================
    # CHOOSE DURATION
    # =====================================================

    if query.data == "choose_duration":

        project = user_projects.get(
            user_id
        )

        if not project:

            await query.edit_message_text(
                "ابتدا روی 🚀 شروع ساخت ویدیو بزن."
            )

            return

        if not project.get("idea"):

            await query.edit_message_text(
                "⚠️ ابتدا ایده ویدیوت را بنویس."
            )

            project["status"] = (
                "waiting_for_idea"
            )

            return

        project["status"] = (
            "waiting_for_duration"
        )

        await query.edit_message_text(

            text=(
                "⏱ مدت ویدیو را انتخاب کن:"
            ),

            reply_markup=duration_keyboard()

        )

        return

    # =====================================================
    # DURATION
    # =====================================================

    if query.data.startswith(
        "duration_"
    ):

        project = user_projects.get(
            user_id
        )

        if not project:
            return

        value = query.data.replace(
            "duration_",
            ""
        )

        if value == "custom":

            project["status"] = (
                "waiting_for_custom_duration"
            )

            await query.edit_message_text(

                text=(
                    "✏️ مدت دلخواه را به ثانیه "
                    "فقط به صورت عدد بفرست.\n\n"
                    "مثلاً:\n"
                    "75"
                )

            )

            return

        duration = int(value)

        project["duration"] = duration

        project["status"] = (
            "waiting_for_image_count"
        )

        await query.edit_message_text(

            text=(
                f"⏱ مدت انتخاب شد: "
                f"{duration} ثانیه\n\n"
                "حالا تعداد تصاویر را انتخاب کن:"
            ),

            reply_markup=image_count_keyboard()

        )

        return

    # =====================================================
    # IMAGE COUNT
    # =====================================================

    if query.data.startswith(
        "images_"
    ):

        project = user_projects.get(
            user_id
        )

        if not project:
            return

        value = query.data.replace(
            "images_",
            ""
        )

        if value == "custom":

            project["status"] = (
                "waiting_for_custom_images"
            )

            await query.edit_message_text(

                text=(
                    "✏️ تعداد تصاویر دلخواه را "
                    "به صورت عدد بفرست.\n\n"
                    "مثلاً:\n"
                    "8"
                )

            )

            return

        image_count = int(value)

        project["image_count"] = image_count

        project["status"] = "ready"

        await query.edit_message_text(

            text=(
                "✅ تنظیمات آماده شد.\n\n"
                f"💡 موضوع:\n"
                f"{project['idea']}\n\n"
                f"⏱ مدت: "
                f"{project['duration']} ثانیه\n"
                f"🖼 تصاویر: "
                f"{project['image_count']}\n\n"
                "همه تصاویر بر اساس یک سناریوی "
                "واحد ساخته می‌شوند."
            ),

            reply_markup=build_keyboard()

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
                "⚠️ پروژه‌ای وجود ندارد."
            )

            return

        if not project.get("idea"):

            await query.edit_message_text(
                "⚠️ ابتدا ایده را وارد کن."
            )

            return

        if not project.get("duration"):

            await query.edit_message_text(
                "⚠️ ابتدا مدت ویدیو را انتخاب کن.",
                reply_markup=duration_keyboard()
            )

            return

        if not project.get("image_count"):

            await query.edit_message_text(
                "⚠️ ابتدا تعداد تصاویر را انتخاب کن.",
                reply_markup=image_count_keyboard()
            )

            return

        await query.edit_message_text(

            text=(
                "🚀 ساخت ویدیو شروع شد.\n\n"
                f"⏱ {project['duration']} ثانیه\n"
                f"🖼 {project['image_count']} تصویر\n\n"
                "لطفاً صبر کن..."
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
                        "🎉 ویدیو آماده شد!\n\n"
                        f"⏱ مدت: "
                        f"{project['duration']} ثانیه\n"
                        f"🖼 تصاویر: "
                        f"{project['image_count']}"
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
                    f"{str(error)[:2500]}"
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

    # =====================================================
    # NO PROJECT
    # =====================================================

    if user_id not in user_projects:

        await send_message(
            update,
            "لطفاً ابتدا /start را بزن."
        )

        return

    project = user_projects[user_id]

    # =====================================================
    # IDEA
    # =====================================================

    if project.get("status") == "waiting_for_idea":

        project["idea"] = text

        project["status"] = (
            "waiting_for_duration"
        )

        await send_message(

            update,

            text=(
                "✅ ایده دریافت شد!\n\n"
                f"💡 موضوع:\n{text}\n\n"
                "حالا مدت ویدیو را انتخاب کن:"
            ),

            reply_markup=duration_keyboard()

        )

        return

    # =====================================================
    # CUSTOM DURATION
    # =====================================================

    if project.get("status") == (
        "waiting_for_custom_duration"
    ):

        try:

            duration = int(text)

            if duration < 5 or duration > 300:

                raise ValueError

        except Exception:

            await send_message(

                update,

                "⚠️ مدت باید عددی بین 5 تا 300 ثانیه باشد."

            )

            return

        project["duration"] = duration

        project["status"] = (
            "waiting_for_image_count"
        )

        await send_message(

            update,

            (
                f"✅ مدت انتخاب شد: "
                f"{duration} ثانیه\n\n"
                "حالا تعداد تصاویر را انتخاب کن:"
            ),

            reply_markup=image_count_keyboard()

        )

        return

    # =====================================================
    # CUSTOM IMAGE COUNT
    # =====================================================

    if project.get("status") == (
        "waiting_for_custom_images"
    ):

        try:

            image_count = int(text)

            if image_count < 1 or image_count > 30:

                raise ValueError

        except Exception:

            await send_message(

                update,

                "⚠️ تعداد تصاویر باید عددی بین 1 تا 30 باشد."

            )

            return

        project["image_count"] = image_count

        project["status"] = "ready"

        await send_message(

            update,

            (
                "✅ تنظیمات کامل شد.\n\n"
                f"⏱ مدت: "
                f"{project['duration']} ثانیه\n"
                f"🖼 تعداد تصاویر: "
                f"{image_count}\n\n"
                "حالا روی 🎬 ساخت ویدیو بزن."
            ),

            reply_markup=build_keyboard()

        )

        return

    # =====================================================
    # READY
    # =====================================================

    if project.get("status") == "ready":

        project["idea"] = text

        await send_message(

            update,

            (
                "✅ موضوع تغییر کرد.\n\n"
                f"💡 {text}\n\n"
                "برای ساخت ویدیو روی دکمه زیر بزن."
            ),

            reply_markup=build_keyboard()

        )

        return

    await send_message(

        update,

        "پیامت دریافت شد ✅"

    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context
):

    print(
        "===================================="
    )

    print(
        "BOT ERROR:"
    )

    print(
        repr(context.error)
    )

    print(
        "===================================="
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        print(
            "ERROR: BOT_TOKEN is not set."
        )

        return

    print(
        "===================================="
    )

    print(
        "AI VIDEO TELEGRAM BOT"
    )

    print(
        "Starting..."
    )

    print(
        "===================================="
    )

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
