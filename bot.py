import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "realestate.db")

logging.basicConfig(level=logging.INFO)

PHOTOS, DETAILS, PRICE, LOCATION, CONTACT = range(5)


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        details TEXT NOT NULL,
        price TEXT,
        location TEXT,
        contact TEXT,
        photo_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        telegram_user_id INTEGER,
        name TEXT,
        phone TEXT,
        budget TEXT,
        status TEXT DEFAULT 'new',
        source TEXT,
        created_at TEXT NOT NULL
    )""")
    con.commit()
    con.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🏠 إضافة عقار"], ["📊 الإحصائيات", "🎯 الـLeads"]]
    await update.message.reply_text(
        "أهلاً يا معاذ 👋\n\nأنا Real Estate Marketing Bot.\n"
        "أقدر أجمع بيانات العقار، أحفظ الـLeads، وبعدها هنضيف النشر التلقائي للمنصات.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return ConversationHandler.END


async def add_property(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["photos"] = []
    await update.message.reply_text("📸 ابعت صور العقار كلها واحدة واحدة.\n\nبعد آخر صورة ابعت كلمة: تم")
    return PHOTOS


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["photos"].append(update.message.photo[-1].file_id)
        await update.message.reply_text(f"✅ وصلت الصورة رقم {len(context.user_data['photos'])}. ابعت باقي الصور أو اكتب تم")
        return PHOTOS
    if update.message.text and update.message.text.strip() == "تم":
        if not context.user_data["photos"]:
            await update.message.reply_text("لازم تبعت صورة واحدة على الأقل.")
            return PHOTOS
        await update.message.reply_text("📝 ابعت تفاصيل العقار في رسالة واحدة، مثال:\n250 متر - 3 غرف - 2 حمام - ريسبشن 4 قطع - مطبخ أمريكان - الدور الخامس")
        return DETAILS
    await update.message.reply_text("ابعت صورة أو اكتب تم بعد ما تخلص الصور.")
    return PHOTOS


async def receive_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["details"] = update.message.text
    await update.message.reply_text("💰 السعر كام؟ اكتب السعر أو (اتصل لمعرفة السعر)")
    return PRICE


async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["price"] = update.message.text
    await update.message.reply_text("📍 اكتب المنطقة/الموقع")
    return LOCATION


async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["location"] = update.message.text
    await update.message.reply_text("📞 اكتب رقم التواصل الذي سيظهر للعميل")
    return CONTACT


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contact"] = update.message.text
    con = db()
    cur = con.execute(
        "INSERT INTO properties(owner_id,details,price,location,contact,photo_count,created_at) VALUES(?,?,?,?,?,?,?)",
        (update.effective_user.id, context.user_data["details"], context.user_data["price"], context.user_data["location"], context.user_data["contact"], len(context.user_data["photos"]), datetime.utcnow().isoformat()),
    )
    property_id = cur.lastrowid
    con.commit()
    con.close()

    caption = (
        f"🏠 عقار جديد #{property_id}\n\n"
        f"📍 {context.user_data['location']}\n"
        f"📐 {context.user_data['details']}\n"
        f"💰 {context.user_data['price']}\n"
        f"📞 {context.user_data['contact']}\n\n"
        "🎯 تم حفظ العقار. الخطوة التالية: توليد الإعلان والنشر تلقائيًا."
    )
    await update.message.reply_text(caption)
    context.user_data.clear()
    return ConversationHandler.END


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con = db()
    properties = con.execute("SELECT COUNT(*) c FROM properties").fetchone()["c"]
    leads = con.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]
    new_leads = con.execute("SELECT COUNT(*) c FROM leads WHERE status='new'").fetchone()["c"]
    con.close()
    await update.message.reply_text(f"📊 الإحصائيات\n\n🏠 العقارات: {properties}\n🎯 كل الـLeads: {leads}\n🟢 Leads جديدة: {new_leads}")


async def leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con = db()
    rows = con.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 20").fetchall()
    con.close()
    if not rows:
        await update.message.reply_text("لسه مفيش Leads 🎯")
        return
    text = "🎯 آخر الـLeads:\n\n"
    for r in rows:
        text += f"#{r['id']} | عقار #{r['property_id']} | {r['name'] or '-'} | {r['phone'] or '-'} | {r['status']}\n"
    await update.message.reply_text(text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🏠 إضافة عقار$"), add_property)],
        states={
            PHOTOS: [MessageHandler(filters.PHOTO | filters.TEXT, receive_photo)],
            DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_details)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_location)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_contact)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex(r"^📊 الإحصائيات$"), stats))
    app.add_handler(MessageHandler(filters.Regex(r"^🎯 الـLeads$"), leads))
    app.run_polling()


if __name__ == "__main__":
    main()
