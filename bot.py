import asyncio
import requests
import time
import difflib
from telethon import TelegramClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, CallbackQueryHandler, ContextTypes
)

# ==== CONFIG ====
api_id = 22467314
api_hash = "08181401f6807cdc954f6c7d8231dfcf"
client = TelegramClient("session", api_id, api_hash)
BOT_TOKEN = "8331381065:AAHBC1-d8luuFnfE3Q13RufYmjghioR9mVQ"
CHANNEL_ID = -1002324737561
BOT_USERNAME = "Official_Jak_Tv_Bot"
AROLINKS_API = "f9b4b4b636cc9dc0791793e78fbca137c3670dfc"

# Store search results per user {user_id: [(msg_id, text, file_info), ...]}
user_search_results = {}
user_pages = {}
search_timers = {}

# ==== START ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        if args[0].startswith("unlock_"):
            parts = args[0].split("_")
            if len(parts) < 3:
                await update.message.reply_text("⚠️ Invalid unlock link.")
                return
            original_user_id = int(parts[1])
            msg_id = int(parts[2])

            if update.message.chat_id != original_user_id:
                await update.message.reply_text("❌ Link is only for the user who requested.")
                return

            try:
                sent = await context.bot.forward_message(
                    chat_id=update.message.chat_id,
                    from_chat_id=CHANNEL_ID,
                    message_id=msg_id
                )
                note = await update.message.reply_text("⏳ This file will auto-delete in 5 minutes!")
                await asyncio.sleep(300)  # 5 minutes
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=sent.message_id)
                await context.bot.delete_message(chat_id=update.message.chat_id, message_id=note.message_id)
            except Exception as e:
                print(f"Unlock error: {e}")
                await update.message.reply_text("⚠️ Failed to retrieve file.")
            return

    await update.message.reply_text("🔍 Send me a keyword to search:")

# ==== SEARCH HANDLER ====
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("❌ Please provide a keyword to search.")
        return
    await handle_search(update, context, query)

# ==== HANDLE SEARCH ====
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query):
    start_time = time.time()
    user_id = update.message.chat_id
    results = []

    try:
        async for msg in client.iter_messages(CHANNEL_ID, search=query, limit=100):
            file_info = await get_file_info(msg)
            if msg.text:
                preview = msg.text.split('\n')[0][:35] + "..." if len(msg.text) > 35 else msg.text
            else:
                preview = f"{file_info['name'][:30]}..." if file_info['name'] else "Media File"
            if file_info['size']:
                preview += f" [{file_info['size']}]"
            if file_info['resolution']:
                preview += f" [{file_info['resolution']}]"
            results.append((msg.id, preview, file_info))
    except Exception as e:
        print(f"Search error: {e}")
        await update.message.reply_text("🔎 Search failed. Please try again later.")
        return

    search_time = round(time.time() - start_time, 2)
    search_timers[user_id] = search_time

    if not results:
        # AI spelling suggestions
        all_words = [m.text.split()[0] for m in await client.get_messages(CHANNEL_ID, limit=200) if m.text]
        suggestions = difflib.get_close_matches(query, list(set(all_words)), n=3, cutoff=0.6)
        suggestion_text = "\n💡 Did you mean: " + ", ".join(suggestions) if suggestions else ""
        await update.message.reply_text(
            f"❌ No results found for '{query}'.{suggestion_text}\nTry different keywords."
        )
        return

    user_search_results[user_id] = results
    user_pages[user_id] = 0

    response_msg = (
        f"ᴛᴏᴛᴀʟ ꜰɪʟᴇꜱ : {len(results)}\n"
        f"ʀᴇsᴜʟᴛ ɪɴ : {search_time} Sᴇᴄᴏɴᴅs\n\n"
        f"🧾 Files below (auto-deletes in 5 min)"
    )

    sent_msg = await update.message.reply_text(response_msg)
    await send_page(update, context, user_id)

    # Auto delete the search header after 5 min
    await asyncio.sleep(300)
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=sent_msg.message_id)
    except:
        pass

# ==== GET FILE INFO ====
async def get_file_info(msg):
    file_info = {'name': '', 'size': '', 'resolution': ''}
    if msg.media and hasattr(msg.media, 'document'):
        doc = msg.media.document
        for attr in doc.attributes:
            if hasattr(attr, 'file_name'):
                file_info['name'] = attr.file_name
        size = doc.size
        if size:
            if size < 1024:
                file_info['size'] = f"{size} B"
            elif size < 1024*1024:
                file_info['size'] = f"{round(size/1024, 1)} KB"
            elif size < 1024*1024*1024:
                file_info['size'] = f"{round(size/(1024*1024), 1)} MB"
            else:
                file_info['size'] = f"{round(size/(1024*1024*1024), 1)} GB"
        for attr in doc.attributes:
            if hasattr(attr, 'w') and hasattr(attr, 'h'):
                file_info['resolution'] = f"{attr.w}x{attr.h}"
    return file_info

# ==== SEND PAGE ====
async def send_page(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id=None):
    if user_id is None:
        user_id = update.message.chat_id if update.message else update.callback_query.message.chat_id

    page = user_pages[user_id]
    results = user_search_results[user_id]
    start_idx = page * 10
    end_idx = start_idx + 10
    page_results = results[start_idx:end_idx]
    keyboard = []

    for mid, text, file_info in page_results:
        callback_data = f"file_{user_id}_{mid}"
        keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"nav_{user_id}_prev"))
    if end_idx < len(results):
        nav_buttons.append(InlineKeyboardButton("➡ Next", callback_data=f"nav_{user_id}_next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    text_msg = f"🔍 Page {page+1} of {len(results)//10 + (1 if len(results)%10 else 0)}"

    if update.message:
        msg = await update.message.reply_text(text_msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        msg = await update.callback_query.edit_message_text(text_msg, reply_markup=InlineKeyboardMarkup(keyboard))

    # Auto delete result list after 5 min
    await asyncio.sleep(300)
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
    except:
        pass

# ==== BUTTON HANDLER ====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.message.chat_id

    if data.startswith("nav_"):
        parts = data.split("_")
        nav_user_id = int(parts[1])
        action = parts[2]
        if user_id != nav_user_id:
            await query.answer("❌ This is another user's request.", show_alert=True)
            return
        if action == "next":
            user_pages[user_id] += 1
        elif action == "prev":
            user_pages[user_id] -= 1
        await send_page(update, context, user_id)
        return

    elif data.startswith("file_"):
        parts = data.split("_")
        file_user_id = int(parts[1])
        msg_id = int(parts[2])
        if user_id != file_user_id:
            await query.answer("❌ Not your request.", show_alert=True)
            return

        unlock_link = f"https://t.me/{BOT_USERNAME}?start=unlock_{file_user_id}_{msg_id}"
        short_url = make_shortlink(unlock_link)
        await query.edit_message_text(
            text=f"✅ Click here to unlock:\n{short_url}\n⚠️ Auto expires in 5 min.",
            disable_web_page_preview=True
        )

# ==== MAKE SHORTLINK ====
def make_shortlink(url):
    try:
        r = requests.get(f"https://arolinks.com/api?api={AROLINKS_API}&url={url}")
        data = r.json()
        return data.get("shortenedUrl", url)
    except Exception as e:
        print(f"Shortlink error: {e}")
        return url

# ==== MAIN ====
def main():
    client.start()
    print("✅ Telethon client started")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
