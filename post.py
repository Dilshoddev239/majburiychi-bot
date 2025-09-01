import sqlite3
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import Forbidden, BadRequest, TelegramError
import re

BOT_TOKEN = "8281683527:AAHNbugo01Cs2PeZKk_5zP9Z0oiN2NlwhsA"

# 🔹 SQLite3 bazasini ishga tushirish
def init_db():
    conn = sqlite3.connect("hikoya.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT,
        message_id INTEGER,
        admin_id INTEGER,
        boshi_text TEXT,
        boshi_type TEXT,
        boshi_file_id TEXT,
        davomi_text TEXT,
        davomi_type TEXT,
        davomi_file_id TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# Kanal username ni to'g'ri formatga keltirish
def format_channel_username(channel_input):
    channel_input = channel_input.strip()
    if not channel_input.startswith('@'):
        channel_input = '@' + channel_input
    return channel_input

# Obuna tekshirish funksiyasi
async def check_subscription(bot, channel_username, user_id):
    try:
        member = await bot.get_chat_member(channel_username, user_id)
        print(f"User {user_id} status in {channel_username}: {member.status}")
        
        # Obuna bo'lgan statuslar
        if member.status in ["member", "administrator", "creator"]:
            return True, "subscribed"
        elif member.status == "left":
            return False, "not_subscribed"
        elif member.status == "kicked":
            return False, "banned"
        else:
            return False, "restricted"
            
    except BadRequest as e:
        print(f"BadRequest error: {e}")
        if "user not found" in str(e).lower():
            return False, "not_subscribed"
        elif "chat not found" in str(e).lower():
            return False, "channel_not_found"
        else:
            return False, "error"
    except Forbidden as e:
        print(f"Forbidden error: {e}")
        return False, "bot_not_admin"
    except TelegramError as e:
        print(f"Telegram error: {e}")
        return False, "error"
    except Exception as e:
        print(f"General error: {e}")
        return False, "error"

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📢 Post yaratish", callback_data="create_post")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Salom!\nPost yaratish uchun tugmani bosing:",
        reply_markup=reply_markup
    )

# Tugma bosilganda
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "create_post":
        await query.message.reply_text("Kanal username kiriting (masalan: @kanal_nomi yoki kanal_nomi):")
        context.user_data["waiting_channel"] = True

# Xabarlar handler
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data

    # 🔹 Kanal username
    if user_data.get("waiting_channel"):
        channel_input = format_channel_username(update.message.text)
        
        # Kanal mavjudligini tekshirish
        try:
            chat_info = await context.bot.get_chat(channel_input)
            if chat_info.type != 'channel':
                await update.message.reply_text("❌ Bu kanal emas! Iltimos, kanal username kiriting.")
                return
            
            user_data["channel"] = channel_input
            user_data["waiting_channel"] = False
            user_data["waiting_boshi"] = True
            await update.message.reply_text("✅ Kanal topildi va qabul qilindi! Hikoya boshi yuboring (matn/rasm/video).")
            
        except BadRequest:
            await update.message.reply_text("❌ Kanal topilmadi! Username to'g'ri ekanligiga ishonch hosil qiling.")
            return
        except Forbidden:
            await update.message.reply_text("❌ Bot ushbu kanalga admin emas!")
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Kanal tekshirishda xatolik: {e}")
            return

    # 🔹 Hikoya boshi
    elif user_data.get("waiting_boshi"):
        if update.message.photo:
            user_data["boshi_type"] = "photo"
            user_data["boshi_file_id"] = update.message.photo[-1].file_id
            user_data["boshi_text"] = update.message.caption_html or ""
        elif update.message.video:
            user_data["boshi_type"] = "video"
            user_data["boshi_file_id"] = update.message.video.file_id
            user_data["boshi_text"] = update.message.caption_html or ""
        else:
            user_data["boshi_type"] = "text"
            user_data["boshi_file_id"] = None
            user_data["boshi_text"] = update.message.text_html

        user_data["waiting_boshi"] = False
        user_data["waiting_davomi"] = True
        await update.message.reply_text("✅ Hikoya boshi saqlandi! Endi davomini yuboring.")

    # 🔹 Hikoya davomi
    elif user_data.get("waiting_davomi"):
        if update.message.photo:
            davomi_type = "photo"
            davomi_file_id = update.message.photo[-1].file_id
            davomi_text = update.message.caption_html or ""
        elif update.message.video:
            davomi_type = "video"
            davomi_file_id = update.message.video.file_id
            davomi_text = update.message.caption_html or ""
        else:
            davomi_type = "text"
            davomi_file_id = None
            davomi_text = update.message.text_html

        channel = user_data["channel"]
        admin_id = update.message.from_user.id

        try:
            channel_msg = None
            
            # Kanalga post yuborish
            if user_data["boshi_type"] == "photo":
                channel_msg = await context.bot.send_photo(
                    chat_id=channel,
                    photo=user_data["boshi_file_id"],
                    caption=user_data["boshi_text"],
                    parse_mode="HTML"
                )
            elif user_data["boshi_type"] == "video":
                channel_msg = await context.bot.send_video(
                    chat_id=channel,
                    video=user_data["boshi_file_id"],
                    caption=user_data["boshi_text"],
                    parse_mode="HTML"
                )
            else:
                channel_msg = await context.bot.send_message(
                    chat_id=channel,
                    text=user_data["boshi_text"],
                    parse_mode="HTML"
                )
            
            # Tugmani qo'shish uchun postni edit qilish
            channel_clean = channel.replace('@', '')
            callback_data = f"see_more_{channel_clean}_{channel_msg.message_id}"
            
            # Callback data uzunligini tekshirish (64 byte limit)
            if len(callback_data.encode('utf-8')) > 64:
                # Agar uzun bo'lsa, qisqartirish
                callback_data = f"more_{channel_clean[:10]}_{channel_msg.message_id}"
            
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("📖 Davomini ko'rish", callback_data=callback_data)]]
            )
            
            # Reply markup qo'shish
            await context.bot.edit_message_reply_markup(
                chat_id=channel,
                message_id=channel_msg.message_id,
                reply_markup=reply_markup
            )

            # 🔹 Ma'lumotni SQLite saqlash
            conn = sqlite3.connect("hikoya.db")
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO posts (channel, message_id, admin_id, boshi_text, boshi_type, boshi_file_id, davomi_text, davomi_type, davomi_file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                channel, channel_msg.message_id, admin_id, user_data["boshi_text"], user_data["boshi_type"], user_data["boshi_file_id"],
                davomi_text, davomi_type, davomi_file_id
            ))
            conn.commit()
            conn.close()

            # 🔹 Adminga postni yuborish
            try:
                channel_url = f"https://t.me/{channel_clean}/{channel_msg.message_id}"
                admin_keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📖 Davomini ko'rish", url=channel_url)]]
                )
                
                if user_data["boshi_type"] == "photo":
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=user_data["boshi_file_id"],
                        caption=user_data["boshi_text"],
                        parse_mode="HTML",
                        reply_markup=admin_keyboard
                    )
                elif user_data["boshi_type"] == "video":
                    await context.bot.send_video(
                        chat_id=admin_id,
                        video=user_data["boshi_file_id"],
                        caption=user_data["boshi_text"],
                        parse_mode="HTML",
                        reply_markup=admin_keyboard
                    )
                else:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=user_data["boshi_text"],
                        parse_mode="HTML",
                        reply_markup=admin_keyboard
                    )
                    
                await update.message.reply_text("✅ Hikoya muvaffaqiyatli kanalga joylandi va sizga ham yuborildi!")
                
            except Exception as admin_error:
                print(f"Admin send error: {admin_error}")
                await update.message.reply_text("✅ Hikoya kanalga joylandi!")

        except Forbidden:
            await update.message.reply_text("❌ Bot kanalga admin emas!")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Xatolik: {e}")

        user_data.clear()

# "Davomini ko'rish" tugmasi
async def see_more_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    print(f"Callback data: {query.data}")  # Debug uchun
    
    # Callback data'dan ma'lumotlarni olish
    if query.data.startswith("see_more_"):
        parts = query.data[9:].split("_")  # "see_more_" qismini olib tashlash
    elif query.data.startswith("more_"):
        parts = query.data[5:].split("_")  # "more_" qismini olib tashlash
    else:
        await query.answer("❌ Noto'g'ri callback data", show_alert=True)
        return
    
    if len(parts) < 2:
        await query.answer("❌ Noto'g'ri callback format", show_alert=True)
        return
    
    try:
        message_id = int(parts[-1])  # Oxirgi qism message_id
        channel_name = "_".join(parts[:-1])  # Qolgan qismlar kanal nomi
        channel_username = f"@{channel_name}"
        
        print(f"Parsed: channel={channel_username}, message_id={message_id}")  # Debug
        
    except (ValueError, IndexError) as e:
        print(f"Parse error: {e}")
        await query.answer("❌ Ma'lumot olishda xatolik", show_alert=True)
        return

    # 🔹 SQLite'dan tegishli postni olish
    conn = sqlite3.connect("hikoya.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT davomi_text, davomi_type, davomi_file_id, admin_id, channel 
        FROM posts 
        WHERE message_id = ? AND (channel = ? OR channel LIKE ?)
    """, (message_id, channel_username, f"%{channel_name}%"))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        await query.answer("❌ Post topilmadi", show_alert=True)
        return
    
    davomi_text, davomi_type, davomi_file_id, admin_id, actual_channel = row
    
    print(f"Found post: channel={actual_channel}, admin={admin_id}")  # Debug

    # 🔹 Agar admin bo'lsa, to'g'ridan-to'g'ri ko'rsatish
    if user_id == admin_id:
        davomi_popup = davomi_text[:200] + "..." if len(davomi_text) > 200 else davomi_text
        await query.answer(f"📖 Hikoya davomi (Admin):\n\n{davomi_popup}", show_alert=True)
        return

    # 🔹 Oddiy foydalanuvchilar uchun obuna tekshirish
    is_subscribed, status = await check_subscription(context.bot, actual_channel, user_id)
    
    if is_subscribed:
        # ✅ Obuna bo'lgan - davomini ko'rsatish
        davomi_popup = davomi_text[:200] + "..." if len(davomi_text) > 200 else davomi_text
        await query.answer(f"📖 Hikoya davomi:\n\n{davomi_popup}", show_alert=True)
    else:
        # ❌ Obuna bo'lmagan - xabar berish
        if status == "not_subscribed":
            await query.answer(f"❌ Davomini ko'rish uchun {actual_channel} kanaliga obuna bo'ling!", show_alert=True)
        elif status == "banned":
            await query.answer(f"❌ Sizga {actual_channel} kanaliga kirish taqiqlangan!", show_alert=True)
        elif status == "channel_not_found":
            await query.answer("❌ Kanal topilmadi!", show_alert=True)
        elif status == "bot_not_admin":
            await query.answer("❌ Bot kanalga admin emas! Admin bilan bog'laning.", show_alert=True)
        else:
            await query.answer(f"❌ Davomini ko'rish uchun {actual_channel} kanaliga obuna bo'ling!", show_alert=True)

# Botni ishga tushirish
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="create_post"))
    app.add_handler(CallbackQueryHandler(see_more_button, pattern=r"^(see_more_|more_)"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
