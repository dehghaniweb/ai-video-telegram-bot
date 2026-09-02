import os
import io
import time
import shutil
import subprocess
import requests

from PIL import Image

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

BASE_DIR = "video_data"

os.makedirs(BASE_DIR, exist_ok=True)


# =========================================================
# MESSAGE MEMORY
# =========================================================

def get_chat_dir(chat_id):
    path = os.path.join(
        BASE_DIR,
        str(chat_id)
    )

    os.makedirs(
        path,
        exist_ok=True
    )

    return path


def get_message_file(chat_id):

    return os.path.join(
        get_chat_dir(chat_id),
        "messages.txt"
    )


def load_message_ids(chat_id):

    filename = get_message_file(chat_id)

    if not os.path.exists(filename):
        return []

    ids = []

    try:
        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                line = line.strip()

                if line.isdigit():
                    ids.append(int(line))

    except Exception:
        pass

    return ids


def save_message_id(chat_id, message_id):

    filename = get_message_file(chat_id)

    try:

        with open(
            filename,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                str(message_id) + "\n"
            )

    except Exception as e:

        print(
            "MESSAGE SAVE ERROR:",
            repr(e)
        )


def clear_saved_message_ids(chat_id):

    filename = get_message_file(chat_id)

    try:

        if os.path.exists(filename):
            os.remove(filename)

    except Exception:
        pass


async def remember_message(update, message):

    if not message:
        return

    chat_id = update.effective_chat.id

    save_message_id(
        chat_id,
        message.message_id
    )


async def send_message(update, text, **kwargs):

    message = await update.effective_chat.send_message(
        text,
        **kwargs
    )

    await remember_message(
        update,
        message
    )

    return message


# =========================================================
# DELETE PREVIOUS BOT MESSAGES
# =========================================================

async def delete_saved_messages(
    context,
    chat_id
):

    message_ids = load_message_ids(
        chat_id
    )

    if not message_ids:
        return

    print(
        f"Deleting {len(message_ids)} saved messages..."
    )

    for message_id in message_ids:

        try:

            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )

        except Exception as e:

            print(
                "DELETE ERROR:",
                message_id,
                repr(e)
            )

    clear_saved_message_ids(
        chat_id
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.clear()

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
                callback_data="restart"
            )
        ]

    ]

    message = await update.message.reply_text(

        "🎬 سازنده ویدیوی تبلیغاتی\n\n"

        "ایده یا محصولت را بنویس.\n\n"

        "مثلاً:\n"
        "🪒 تبلیغ ماشین اصلاح صورت\n\n"

        "یا:\n"
        "🌾 تبلیغ کود گیاهی برای گندم\n\n"

        "یا:\n"
        "👟 تبلیغ کفش ورزشی",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

    await remember_message(
        update,
        message
    )


# =========================================================
# RESTART
# =========================================================

async def restart(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    chat_id = update.effective_chat.id

    # پاک کردن پیام‌های قبلی ثبت‌شده
    await delete_saved_messages(
        context,
        chat_id
    )

    # پاک کردن اطلاعات قبلی
    context.user_data.clear()

    # ساخت پیام جدید
    keyboard = [

        [
            InlineKeyboardButton(
                "🚀 شروع ساخت ویدیو",
                callback_data="start_video"
            )
        ]

    ]

    message = await context.bot.send_message(

        chat_id=chat_id,

        text=(
            "🔄 شروع مجدد شد.\n\n"
            "✍️ ایده تبلیغاتی خودت را بنویس.\n\n"
            "مثلاً:\n"
            "تبلیغ ماشین اصلاح صورت"
        ),

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

    await remember_message(
        update,
        message
    )


# =========================================================
# START VIDEO
# =========================================================

async def start_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    context.user_data["step"] = "idea"

    message = await query.message.reply_text(

        "✍️ ایده تبلیغاتی را بنویس:\n\n"

        "مثلاً:\n"
        "تبلیغ ماشین اصلاح صورت\n\n"

        "یا:\n"
        "تبلیغ کود گیاهی برای گندم"
    )

    await remember_message(
        update,
        message
    )


# =========================================================
# SUBJECT DETECTION
# =========================================================

def detect_subject(idea):

    text = idea.lower()

    agriculture_words = [
        "کشاور",
        "مزرعه",
        "کود",
        "بذر",
        "سم",
        "گندم",
        "ذرت",
        "جو",
        "برنج",
        "گوجه",
        "خیار",
        "پسته",
        "انگور",
        "سیب",
        "زعفران",
        "گلخانه",
        "آبیاری",
        "تراکتور",
        "نهال",
        "باغ",
        "گیاه"
    ]

    grooming_words = [
        "ماشین اصلاح",
        "اصلاح صورت",
        "ریش تراش",
        "ریش‌تراش",
        "تریمر",
        "موزر"
    ]

    shoe_words = [
        "کفش",
        "کتانی",
        "کفش ورزشی"
    ]

    phone_words = [
        "گوشی",
        "موبایل",
        "تلفن همراه"
    ]

    perfume_words = [
        "عطر",
        "ادکلن",
        "پرفیوم"
    ]

    food_words = [
        "غذا",
        "خوراکی",
        "شکلات",
        "بیسکویت",
        "نوشیدنی",
        "آبمیوه"
    ]

    cosmetic_words = [
        "کرم",
        "لوازم آرایش",
        "رژ",
        "شامپو",
        "صابون"
    ]

    if any(
        word in text
        for word in agriculture_words
    ):
        return "agriculture"

    if any(
        word in text
        for word in grooming_words
    ):
        return "grooming"

    if any(
        word in text
        for word in shoe_words
    ):
        return "shoes"

    if any(
        word in text
        for word in phone_words
    ):
        return "electronics"

    if any(
        word in text
        for word in perfume_words
    ):
        return "perfume"

    if any(
        word in text
        for word in food_words
    ):
        return "food"

    if any(
        word in text
        for word in cosmetic_words
    ):
        return "cosmetics"

    return "general"


# =========================================================
# SCENE TYPES
# =========================================================

SCENE_TYPES = {

    "agriculture": [

        """
Beautiful realistic agricultural field.
Show the advertised agricultural product prominently
as the hero product in the foreground.
The crop and farming environment must be clearly visible.
""",

        """
A real farmer in the same field examining and using
the advertised agricultural product.
The product must remain clearly visible.
""",

        """
Close-up commercial shot of the agricultural product
being used correctly in the real farming environment.
Show the crop clearly.
""",

        """
Detailed close-up of healthy plants and crops
associated with the advertised product.
Keep the product visible in the composition.
""",

        """
Wide cinematic view of the successful agricultural field.
Healthy crops dominate the environment.
The advertised product is clearly displayed.
""",

        """
Premium final agricultural advertising shot.
Successful farm, healthy crops and the advertised product
together in one strong commercial composition.
"""
    ],


    "grooming": [

        """
Premium bathroom or modern grooming environment.
Show the advertised electric facial shaver prominently
as the hero product.
""",

        """
A well-groomed male model holding and examining
the same electric facial shaver.
The product must be clearly visible.
""",

        """
Close-up of the same electric facial shaver
being used on the man's face.
Focus strongly on the product and shaving action.
""",

        """
Detailed macro commercial shot of the shaver head,
blades and premium product design.
Clean professional grooming environment.
""",

        """
The same man has a clean, smooth and well-groomed face
after using the shaver.
Show the product clearly beside him.
""",

        """
Premium final product advertisement.
The electric facial shaver is the hero object
in a stylish clean grooming environment.
"""
    ],


    "shoes": [

        """
Premium athletic environment.
Show the advertised shoes prominently
as the hero product.
""",

        """
Athlete putting on the same shoes.
Focus on the shoes rather than the person's face.
""",

        """
Dynamic realistic running scene.
Clearly show the same advertised shoes in action.
""",

        """
Close-up commercial shot of the shoe material,
sole, stitching and design.
""",

        """
Athlete performing successfully while wearing
the advertised shoes.
The shoes remain clearly visible.
""",

        """
Premium final shoe advertisement.
The shoes are displayed prominently
with a stylish athletic background.
"""
    ],


    "electronics": [

        """
Modern premium environment.
Show the advertised smartphone prominently
as the hero product.
""",

        """
A person holding the same smartphone.
Focus primarily on the device and its design.
""",

        """
Close-up of the smartphone screen, camera,
buttons and premium materials.
""",

        """
Realistic everyday use of the same smartphone.
Keep the phone clearly visible.
""",

        """
Premium lifestyle scene showing the benefits
of using the same smartphone.
""",

        """
Final premium smartphone advertising hero shot.
The phone dominates the composition.
"""
    ],


    "perfume": [

        """
Luxury environment with elegant lighting.
Show the advertised perfume bottle prominently.
""",

        """
A stylish model interacting with the same perfume.
Keep the bottle as the main subject.
""",

        """
Extreme close-up of the perfume bottle,
glass, cap and liquid details.
""",

        """
Elegant lifestyle scene suggesting the experience
of using the same perfume.
""",

        """
Premium beauty advertising composition.
The perfume bottle remains highly visible.
""",

        """
Final luxury perfume hero shot.
The bottle is the dominant visual element.
"""
    ],


    "food": [

        """
Beautiful appetizing commercial scene.
Show the advertised food or drink prominently.
""",

        """
A person enjoying the same product.
The product must remain the visual focus.
""",

        """
Close-up macro food photography showing
texture, freshness and product details.
""",

        """
Professional commercial serving scene
with the same product clearly visible.
""",

        """
Appetizing lifestyle scene centered around
the advertised product.
""",

        """
Final premium food advertising hero shot.
The product is prominently displayed.
"""
    ],


    "cosmetics": [

        """
Clean premium beauty environment.
Show the advertised cosmetic product prominently.
""",

        """
A model using the same cosmetic product.
The product must remain clearly visible.
""",

        """
Macro commercial shot of the product packaging,
texture and details.
""",

        """
Professional beauty scene showing the product
in realistic use.
""",

        """
Elegant result-focused beauty advertising scene.
Keep the product visible.
""",

        """
Final premium cosmetic product hero shot.
"""
    ],


    "general": [

        """
Professional commercial establishing shot.
Show the exact advertised product prominently.
""",

        """
A realistic person interacting directly
with the same advertised product.
""",

        """
Close-up commercial product photography
of the same product.
""",

        """
Show the product being used realistically
in an environment appropriate to that product.
""",

        """
Show the positive result or benefit of the product.
Keep the same product visible.
""",

        """
Premium final advertising hero shot.
The exact product is the main visual subject.
"""
    ]
}


# =========================================================
# PROMPT GENERATOR
# =========================================================

def create_scene_prompts(
    idea,
    count
):

    subject_type = detect_subject(
        idea
    )

    scene_templates = SCENE_TYPES[
        subject_type
    ]

    prompts = []

    for i in range(count):

        scene_template = scene_templates[
            i % len(scene_templates)
        ]

        prompt = f"""
CREATE SCENE {i + 1} OF {count}
FOR ONE CONTINUOUS PROFESSIONAL PRODUCT COMMERCIAL.

USER'S ORIGINAL IDEA:
{idea}

PRODUCT CATEGORY:
{subject_type}

SCENE:
{scene_template}

CRITICAL RULE:

The exact product described by the user is the MAIN SUBJECT.

Every scene must clearly relate to:

{idea}

Do not replace the product with another product.

Do not create a generic unrelated scene.

VISUAL CONTINUITY:

Use the SAME product design,
same product identity,
same general environment,
same lighting style,
same cinematic style
throughout the entire video.

If a person is present,
use the same person appearance and clothing
throughout the scenes.

The person is secondary.
The PRODUCT is primary.

The scene must look like a REAL COMMERCIAL,
not a random AI image.

STRICTLY FORBIDDEN:

random people,
unrelated people,
generic portraits,
unrelated objects,
unrelated products,
office,
conference room,
business meeting,
random indoor room,
bedroom,
kitchen,
city scene,
unrelated landscape,
generic stock photography,
generic corporate photography,
fantasy objects,
different product,
different brand,
different product design.

If the product is agricultural,
the environment MUST be agricultural.

If the product is a grooming product,
use an appropriate clean grooming environment.

If the product is shoes,
use an appropriate athletic/lifestyle environment.

If the product is electronics,
use an appropriate modern environment.

If the product is perfume or cosmetics,
use an appropriate premium beauty environment.

The environment must ALWAYS match the product.

STYLE:

photorealistic,
professional commercial photography,
cinematic,
premium advertising,
high detail,
realistic materials,
realistic lighting,
natural shadows,
professional camera,
vertical 9:16 composition,
sharp product details,
beautiful composition.

IMPORTANT:

NO TEXT.

NO WATERMARK.

NO RANDOM LOGOS.

NO INVENTED BRAND NAME.

The product must be immediately recognizable.

The image must look like a frame from
a professional advertising campaign.
"""

        prompts.append(
            prompt
        )

    return prompts


# =========================================================
# IMAGE GENERATION
# =========================================================

def generate_image(
    prompt,
    filename
):

    encoded_prompt = requests.utils.quote(
        prompt
    )

    url = (
        "https://image.pollinations.ai/prompt/"
        + encoded_prompt
    )

    params = {

        "model": "flux",

        "width": 720,

        "height": 1280,

        "nologo": "true"

    }

    response = requests.get(
        url,
        params=params,
        timeout=180
    )

    response.raise_for_status()

    image = Image.open(
        io.BytesIO(
            response.content
        )
    )

    image = image.convert(
        "RGB"
    )

    image.save(
        filename,
        quality=95
    )

    return filename


# =========================================================
# VIDEO CREATION
# =========================================================

def create_video_from_images(
    image_files,
    output_file,
    total_duration
):

    if not image_files:
        raise Exception(
            "No images found"
        )

    image_count = len(
        image_files
    )

    duration_per_image = (
        total_duration /
        image_count
    )

    temp_dir = os.path.join(
        os.path.dirname(output_file),
        "frames"
    )

    if os.path.exists(
        temp_dir
    ):

        shutil.rmtree(
            temp_dir
        )

    os.makedirs(
        temp_dir
    )

    frame_rate = 24

    frame_number = 0

    for image_file in image_files:

        image = Image.open(
            image_file
        ).convert(
            "RGB"
        )

        target_width = 720
        target_height = 1280

        image.thumbnail(
            (
                target_width,
                target_height
            ),
            Image.Resampling.LANCZOS
        )

        canvas = Image.new(
            "RGB",
            (
                target_width,
                target_height
            ),
            "black"
        )

        x = (
            target_width -
            image.width
        ) // 2

        y = (
            target_height -
            image.height
        ) // 2

        canvas.paste(
            image,
            (
                x,
                y
            )
        )

        frames_for_image = max(
            1,
            round(
                duration_per_image *
                frame_rate
            )
        )

        for _ in range(
            frames_for_image
        ):

            frame_path = os.path.join(
                temp_dir,
                f"frame_{frame_number:06d}.jpg"
            )

            canvas.save(
                frame_path,
                quality=90
            )

            frame_number += 1

    ffmpeg = shutil.which(
        "ffmpeg"
    )

    if not ffmpeg:

        raise Exception(
            "FFmpeg not found"
        )

    input_pattern = os.path.join(
        temp_dir,
        "frame_%06d.jpg"
    )

    command = [

        ffmpeg,

        "-y",

        "-framerate",
        str(frame_rate),

        "-i",
        input_pattern,

        "-vf",
        (
            "scale=720:1280:"
            "force_original_aspect_ratio=decrease,"
            "pad=720:1280:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p"
        ),

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-crf",
        "23",

        "-movflags",
        "+faststart",

        output_file
    ]

    subprocess.run(
        command,
        check=True
    )

    shutil.rmtree(
        temp_dir
    )

    return output_file


# =========================================================
# DURATION MENU
# =========================================================

async def ask_duration(
    update,
    context
):

    keyboard = [

        [
            InlineKeyboardButton(
                "30 ثانیه",
                callback_data="duration_30"
            ),

            InlineKeyboardButton(
                "45 ثانیه",
                callback_data="duration_45"
            )
        ],

        [
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

    ]

    message = await update.effective_chat.send_message(

        "⏱ مدت ویدیو را انتخاب کن:\n\n"
        "حداقل مدت: ۳۰ ثانیه",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

    await remember_message(
        update,
        message
    )


# =========================================================
# IMAGE COUNT MENU
# =========================================================

async def ask_image_count(
    update,
    context
):

    keyboard = [

        [
            InlineKeyboardButton(
                "6 عکس",
                callback_data="images_6"
            ),

            InlineKeyboardButton(
                "9 عکس",
                callback_data="images_9"
            )
        ],

        [
            InlineKeyboardButton(
                "12 عکس",
                callback_data="images_12"
            )
        ],

        [
            InlineKeyboardButton(
                "✏️ تعداد دلخواه",
                callback_data="images_custom"
            )
        ]

    ]

    message = await update.effective_chat.send_message(

        "🖼 تعداد تصاویر را انتخاب کن:\n\n"
        "حداقل: ۶ تصویر",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

    await remember_message(
        update,
        message
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    data = query.data

    # -----------------------------
    # RESTART
    # -----------------------------

    if data == "restart":

        await restart(
            update,
            context
        )

        return

    # -----------------------------
    # START
    # -----------------------------

    if data == "start_video":

        await start_video(
            update,
            context
        )

        return

    # -----------------------------
    # DURATION
    # -----------------------------

    if data.startswith(
        "duration_"
    ):

        value = data.replace(
            "duration_",
            ""
        )

        if value == "custom":

            context.user_data[
                "step"
            ] = "custom_duration"

            message = await query.message.reply_text(

                "⏱ مدت ویدیو را به ثانیه بنویس.\n\n"
                "حداقل ۳۰ ثانیه.\n"
                "مثلاً: 75"
            )

            await remember_message(
                update,
                message
            )

            return

        duration = int(
            value
        )

        context.user_data[
            "duration"
        ] = duration

        await ask_image_count(
            update,
            context
        )

        return

    # -----------------------------
    # IMAGES
    # -----------------------------

    if data.startswith(
        "images_"
    ):

        value = data.replace(
            "images_",
            ""
        )

        if value == "custom":

            context.user_data[
                "step"
            ] = "custom_images"

            message = await query.message.reply_text(

                "🖼 تعداد تصاویر را وارد کن.\n\n"
                "حداقل ۶ تصویر.\n"
                "مثلاً: 8"
            )

            await remember_message(
                update,
                message
            )

            return

        image_count = int(
            value
        )

        context.user_data[
            "image_count"
        ] = image_count

        await build_video(
            update,
            context
        )

        return


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update,
    context
):

    text = update.message.text.strip()

    step = context.user_data.get(
        "step"
    )

    # -----------------------------
    # IDEA
    # -----------------------------

    if step == "idea":

        context.user_data[
            "idea"
        ] = text

        context.user_data[
            "step"
        ] = "duration"

        await ask_duration(
            update,
            context
        )

        return

    # -----------------------------
    # CUSTOM DURATION
    # -----------------------------

    if step == "custom_duration":

        try:

            duration = int(
                text
            )

            if duration < 30:

                message = await update.message.reply_text(
                    "❌ حداقل مدت ویدیو ۳۰ ثانیه است."
                )

                await remember_message(
                    update,
                    message
                )

                return

            if duration > 300:

                message = await update.message.reply_text(
                    "❌ حداکثر مدت ویدیو ۳۰۰ ثانیه است."
                )

                await remember_message(
                    update,
                    message
                )

                return

            context.user_data[
                "duration"
            ] = duration

            await ask_image_count(
                update,
                context
            )

        except ValueError:

            message = await update.message.reply_text(
                "❌ فقط عدد وارد کن.\nمثلاً: 75"
            )

            await remember_message(
                update,
                message
            )

        return

    # -----------------------------
    # CUSTOM IMAGES
    # -----------------------------

    if step == "custom_images":

        try:

            count = int(
                text
            )

            if count < 6:

                message = await update.message.reply_text(
                    "❌ حداقل ۶ تصویر لازم است."
                )

                await remember_message(
                    update,
                    message
                )

                return

            if count > 30:

                message = await update.message.reply_text(
                    "❌ حداکثر ۳۰ تصویر است."
                )

                await remember_message(
                    update,
                    message
                )

                return

            context.user_data[
                "image_count"
            ] = count

            await build_video(
                update,
                context
            )

        except ValueError:

            message = await update.message.reply_text(
                "❌ فقط عدد وارد کن.\nمثلاً: 8"
            )

            await remember_message(
                update,
                message
            )

        return


# =========================================================
# BUILD VIDEO
# =========================================================

async def build_video(
    update,
    context
):

    chat_id = update.effective_chat.id

    idea = context.user_data.get(
        "idea",
        ""
    )

    duration = context.user_data.get(
        "duration",
        30
    )

    image_count = context.user_data.get(
        "image_count",
        6
    )

    work_dir = os.path.join(
        BASE_DIR,
        str(chat_id),
        "current_video"
    )

    if os.path.exists(
        work_dir
    ):

        shutil.rmtree(
            work_dir
        )

    os.makedirs(
        work_dir,
        exist_ok=True
    )

    progress = await send_message(

        update,

        (
            "🎬 ساخت ویدیو شروع شد.\n\n"

            f"💡 موضوع:\n{idea}\n\n"

            f"⏱ مدت: {duration} ثانیه\n"

            f"🖼 تصاویر: {image_count}\n\n"

            "🧠 در حال تشخیص نوع محصول و طراحی سناریو..."
        )
    )

    try:

        subject_type = detect_subject(
            idea
        )

        prompts = create_scene_prompts(
            idea,
            image_count
        )

        await progress.edit_text(

            (
                "🎬 سناریو آماده شد.\n\n"

                f"📌 نوع محصول: {subject_type}\n"

                f"🖼 تعداد تصاویر: {image_count}\n\n"

                "🎨 در حال تولید تصاویر..."
            )
        )

        image_files = []

        for i, prompt in enumerate(
            prompts
        ):

            await progress.edit_text(

                (
                    "🎨 در حال تولید تصاویر...\n\n"

                    f"🖼 تصویر {i + 1} از "
                    f"{image_count}\n\n"

                    f"📌 محصول: {idea}"
                )
            )

            filename = os.path.join(

                work_dir,

                f"image_{i + 1}.jpg"
            )

            generate_image(
                prompt,
                filename
            )

            image_files.append(
                filename
            )

            time.sleep(1)

        await progress.edit_text(

            "🎞 تمام تصاویر آماده شدند.\n\n"
            "در حال ساخت ویدیوی MP4..."
        )

        output_file = os.path.join(

            work_dir,

            "final_video.mp4"
        )

        create_video_from_images(

            image_files,

            output_file,

            duration
        )

        await progress.edit_text(
            "📤 ویدیو آماده شد.\n\n"
            "در حال ارسال..."
        )

        with open(
            output_file,
            "rb"
        ) as video:

            await update.effective_chat.send_video(

                video=video,

                caption=(

                    "✅ ویدیوی تبلیغاتی آماده شد.\n\n"

                    f"💡 موضوع: {idea}\n"

                    f"⏱ مدت: {duration} ثانیه\n"

                    f"🖼 تصاویر: {image_count}"
                ),

                supports_streaming=True
            )

        context.user_data.clear()

        keyboard = [

            [
                InlineKeyboardButton(
                    "🚀 ساخت ویدیوی جدید",
                    callback_data="start_video"
                )
            ],

            [
                InlineKeyboardButton(
                    "🗑 شروع مجدد",
                    callback_data="restart"
                )
            ]

        ]

        message = await update.effective_chat.send_message(

            "برای ساخت ویدیوی بعدی:",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        await remember_message(
            update,
            message
        )

    except Exception as e:

        print(
            "VIDEO ERROR:",
            repr(e)
        )

        try:

            await progress.edit_text(

                "❌ خطا در ساخت ویدیو.\n\n"

                f"{str(e)[:1500]}"
            )

        except Exception:
            pass


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is not configured"
        )

    app = (
        Application.builder()
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
        CallbackQueryHandler(
            button_handler
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT &
            ~filters.COMMAND,
            text_handler
        )
    )

    print(
        "AI Video Telegram Bot is running..."
    )

    app.run_polling()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()
