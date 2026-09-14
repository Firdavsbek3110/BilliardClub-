"""
🎱 BILLIARD CLUB — Telegram Tasdiqlash Boti
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Python + Flask + pyTelegramBotAPI

Bot vazifasi:
1. Foydalanuvchi /start yuboradi → salomlashadi
2. Loginini so'raydi
3. Foydalanuvchi loginini yuboradi
4. Bot 6 xonali kod yaratadi
5. Kodni inline keyboard bilan yuboradi
6. Sayt avtomatik kodni oladi (polling)

Ishga tushirish: python3 bot.py
"""

import os
import time
import random
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot
from telebot import types

# ═══════════════════════════════════════════════════════════
# ⚙️ SOZLAMALAR — BU YERNI O'ZGARTIRING!
# ═══════════════════════════════════════════════════════════
BOT_TOKEN = "8977154075:AAGXq9oo7y-S2wd-8J-XYgHgx8UPvjzzWHQ"
ADMIN_CHAT_ID = "6120377805"

# Server porti (Railway/Render o'zi beradi)
PORT = int(os.environ.get("PORT", 5000))

# Kod amal qilish muddati (soniyalarda)
CODE_VALIDITY_SECONDS = 300  # 5 daqiqa

# Ro'yxatdan o'tish so'rovi amal qilish muddati
REGISTRATION_VALIDITY_SECONDS = 600  # 10 daqiqa

# ═══════════════════════════════════════════════════════════
# 🌐 FLASK APP
# ═══════════════════════════════════════════════════════════
app = Flask(__name__)
CORS(app)  # Ishlab chiqishda barcha domenga ruxsat (production'da cheklang!)

# ═══════════════════════════════════════════════════════════
# 🤖 TELEGRAM BOT
# ═══════════════════════════════════════════════════════════
bot = telebot.TeleBot(BOT_TOKEN)

# ═══════════════════════════════════════════════════════════
# 💾 IN-MEMORY STORAGE
# Production uchun Redis ishlatishni tavsiya qilaman!
# ═══════════════════════════════════════════════════════════

# {sessionId: {username, fullName, phone, tablesCount, created_at, expires_at}}
pending_registrations = {}

# {sessionId: {code, expires_at, chat_id, username, created_at}}
issued_codes = {}

# {telegram_chat_id: {state, username, sessionId, created_at}}
user_sessions = {}

# Statistika
stats = {
    "total_registrations": 0,
    "total_codes_issued": 0,
    "total_bot_users": 0,
    "started_at": time.time()
}

# ═══════════════════════════════════════════════════════════
# 🛠️ YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════

def generate_code():
    """6 xonali tasdiqlash kodi"""
    return str(random.randint(100000, 999999))

def format_time(seconds):
    """Soniyalarni MM:SS formatiga o'tkazish"""
    if seconds < 0:
        seconds = 0
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"

def cleanup_expired():
    """Muddati o'tgan yozuvlarni tozalash"""
    now = time.time()
    
    # Expired codes
    expired_codes = [k for k, v in issued_codes.items() if v['expires_at'] < now]
    for k in expired_codes:
        del issued_codes[k]
    
    # Expired registrations
    expired_regs = [k for k, v in pending_registrations.items() 
                    if v.get('expires_at', 0) < now]
    for k in expired_regs:
        del pending_registrations[k]
    
    return len(expired_codes), len(expired_regs)

def find_pending_by_username(username):
    """Username bo'yicha pending registration topish"""
    cleanup_expired()
    username_lower = username.strip().lower()
    
    for session_id, data in pending_registrations.items():
        if data['username'].lower() == username_lower:
            if data.get('expires_at', 0) > time.time():
                return session_id, data
    return None, None

def get_role_label(role):
    """Rol uchun chiroyli label"""
    roles = {
        "main_admin": "👑 BOSH ADMIN",
        "admin": "🛡️ ADMIN",
        "user": "👤 FOYDALANUVCHI"
    }
    return roles.get(role, "👤 FOYDALANUVCHI")

# ═══════════════════════════════════════════════════════════
# 🤖 BOT HANDLERLARI
# ═══════════════════════════════════════════════════════════

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Bot /start buyrug'iga javob"""
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "Do'stim"
    username_tg = message.from_user.username
    
    # Foydalanuvchi sessiyasini boshlash
    user_sessions[chat_id] = {
        "state": "waiting_login",
        "created_at": time.time()
    }
    
    stats["total_bot_users"] = len(user_sessions)
    
    welcome_text = (
        f"👋 <b>Assalomu alaykum, {user_name}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎱 <b>BILLIARD CLUB</b> tasdiqlash botiga\n"
        f"xush kelibsiz!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>RO'YXATDAN O'TISH TARTIBI:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>1️⃣</b> Saytda ma'lumotlaringizni kiriting\n"
        f"<b>2️⃣</b> \"TASDIQLASH\" tugmasini bosing\n"
        f"<b>3️⃣</b> <b>Shu botga loginingizni yuboring</b>\n"
        f"<b>4️⃣</b> Bot sizga <b>6 xonali kod</b> yuboradi\n"
        f"<b>5️⃣</b> Kod avtomatik saytga tushadi ✅\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>Endi loginingizni yuboring:</b>\n\n"
        f"<i>Masalan: </i><code>firdavs_01</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"❓ Yordam kerakmi? /help"
    )
    
    bot.send_message(chat_id, welcome_text, parse_mode='HTML')


@bot.message_handler(commands=['help'])
def handle_help(message):
    """Bot /help buyrug'iga javob"""
    help_text = (
        f"❓ <b>YORDAM MARKAZI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 <b>Buyruqlar:</b>\n"
        f"• /start — Boshidan boshlash\n"
        f"• /mycode — Kodni qayta olish\n"
        f"• /help — Yordam\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>QANDAY ISHLAYDI?</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>1.</b> Saytda ro'yxatdan o'ting\n"
        f"<b>2.</b> \"TASDIQLASH\" tugmasini bosing\n"
        f"<b>3.</b> Bu botga <b>/start</b> yuboring\n"
        f"<b>4.</b> Botga <b>loginingizni</b> yuboring\n"
        f"<b>5.</b> Bot sizga <b>6 xonali kod</b> yuboradi\n"
        f"<b>6.</b> Kod avtomatik saytga tushadi ✅\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆘 <b>Muammo bo'lsa:</b>\n\n"
        f"📞 +998 97 757 31 10\n"
        f"📍 Mindonobod Yangi Asr"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')


@bot.message_handler(commands=['mycode'])
def handle_mycode(message):
    """Foydalanuvchi kodini qayta olish"""
    chat_id = message.chat.id
    session = user_sessions.get(chat_id, {})
    
    if session.get('state') != 'code_sent':
        bot.send_message(
            chat_id,
            "❌ <b>Sizda faol kod yo'q!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Avval saytda ro'yxatdan o'ting va\n"
            "botga loginingizni yuboring.",
            parse_mode='HTML'
        )
        return
    
    session_id = session.get('sessionId')
    if session_id and session_id in issued_codes:
        code_data = issued_codes[session_id]
        
        if code_data['expires_at'] > time.time():
            remaining = int(code_data['expires_at'] - time.time())
            code = code_data['code']
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton(
                text="📋 KODNI NUSXALASH",
                callback_data=f"copy_{code}"
            ))
            
            bot.send_message(
                chat_id,
                f"🔐 <b>SIZNING KODINGIZ:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<code>{code}</code>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏱ Qolgan vaqt: <b>{format_time(remaining)}</b>\n\n"
                f"💡 Kodni saytga kiriting",
                parse_mode='HTML',
                reply_markup=markup
            )
        else:
            bot.send_message(
                chat_id,
                "⏱ <b>Kod muddati tugagan!</b>\n\n"
                "Qaytadan kod olish uchun /start yuboring.",
                parse_mode='HTML'
            )
    else:
        bot.send_message(
            chat_id,
            "❌ Kod topilmadi. /start bilan qaytadan boshlang."
        )


@bot.message_handler(func=lambda m: user_sessions.get(m.chat.id, {}).get("state") == "waiting_login")
def handle_login_input(message):
    """Foydalanuvchi loginini qabul qilish va kod yuborish"""
    chat_id = message.chat.id
    username = (message.text or "").strip()
    
    # ═══ VALIDATSIYA ═══
    if not username or len(username) < 3:
        bot.send_message(
            chat_id,
            "⚠️ <b>Login juda qisqa!</b>\n\n"
            "Login kamida <b>3 ta belgidan</b> iborat bo'lishi kerak.\n\n"
            "Qaytadan yuboring:",
            parse_mode='HTML'
        )
        return
    
    if len(username) > 30:
        bot.send_message(
            chat_id,
            "⚠️ <b>Login juda uzun!</b>\n\n"
            "Login maksimal <b>30 ta belgi</b> bo'lishi kerak.\n\n"
            "Qaytadan yuboring:",
            parse_mode='HTML'
        )
        return
    
    # Faqat harf, raqam va pastki chiziq
    clean = username.replace("_", "").replace("-", "")
    if not clean.isalnum():
        bot.send_message(
            chat_id,
            "⚠️ <b>Login formati xato!</b>\n\n"
            "Login faqat <b>harf, raqam, _ va -</b>\n"
            "belgilaridan iborat bo'lsin.\n\n"
            "Masalan: <code>firdavs_01</code>\n\n"
            "Qaytadan yuboring:",
            parse_mode='HTML'
        )
        return
    
    # ═══ PENDING REGISTRATIONNI TOPISH ═══
    session_id, session_data = find_pending_by_username(username)
    
    if not session_id:
        # Login topilmadi
        error_text = (
            f"❌ <b>LOGIN TOPILMADI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 <code>{username}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>Nima qilish kerak?</b>\n\n"
            f"<b>1.</b> Avval <b>saytda</b> ro'yxatdan o'ting\n"
            f"<b>2.</b> \"TASDIQLASH\" tugmasini bosing\n"
            f"<b>3.</b> Keyin bu botga loginni yuboring\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔄 Yoki loginni qaytadan yuboring:"
        )
        bot.send_message(chat_id, error_text, parse_mode='HTML')
        return
    
    # ═══ KOD YARATISH ═══
    code = generate_code()
    expires_at = time.time() + CODE_VALIDITY_SECONDS
    
    issued_codes[session_id] = {
        'code': code,
        'expires_at': expires_at,
        'chat_id': chat_id,
        'username': username,
        'created_at': time.time()
    }
    
    stats["total_codes_issued"] += 1
    
    # Foydalanuvchi sessiyasini yangilash
    user_sessions[chat_id] = {
        "state": "code_sent",
        "username": username,
        "sessionId": session_id,
        "code": code,
        "created_at": time.time()
    }
    
    # ═══ INLINE KEYBOARD — NUSXALASH TUGMASI ═══
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    copy_btn = types.InlineKeyboardButton(
        text="📋 KODNI NUSXALASH",
        callback_data=f"copy_{code}"
    )
    
    mycode_btn = types.InlineKeyboardButton(
        text="🔄 KODNI QAYTA OLISH",
        callback_data="refresh_code"
    )
    
    markup.add(copy_btn, mycode_btn)
    
    # ═══ KODNI YUBORISH ═══
    success_text = (
        f"✅ <b>TASDIQLASH KODI TAYYOR!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>{session_data['fullName']}</b>\n"
        f"🔑 Login: <code>{username}</code>\n"
        f"📞 Telefon: <code>{session_data['phone']}</code>\n"
        f"🎱 Stollar: <b>{session_data['tablesCount']} ta</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔐 <b>SIZNING TASDIQLASH KODINGIZ:</b>\n\n"
        f"<code>{code}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ Kod <b>{format_time(CODE_VALIDITY_SECONDS)}</b> amal qiladi\n\n"
        f"⚠️ <b>Diqqat!</b>\n"
        f"• Kodni hech kimga bermang\n"
        f"• Saytga kiriting — <b>avtomatik tasdiqlanadi</b> ✨\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Kodni nusxalash uchun pastdagi\n"
        f"tugmani bosing 👇"
    )
    
    bot.send_message(
        chat_id,
        success_text,
        parse_mode='HTML',
        reply_markup=markup
    )
    
    # ═══ ADMINNI XABARDOR QILISH ═══
    try:
        now_str = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        
        admin_text = (
            f"🔔 <b>YANGI KOD YUBORILDI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>{session_data['fullName']}</b>\n"
            f"🔑 Login: <code>{username}</code>\n"
            f"📞 Telefon: <code>{session_data['phone']}</code>\n"
            f"🎱 Stollar: <b>{session_data['tablesCount']} ta</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔐 Kod: <code>{code}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {now_str}\n"
            f"📱 TG: @{username_tg or 'yo`q'}"
        )
        
        bot.send_message(ADMIN_CHAT_ID, admin_text, parse_mode='HTML')
    except Exception as e:
        print(f"⚠️ Admin xabar xatosi: {e}")


@bot.message_handler(func=lambda m: True)
def handle_other(message):
    """Boshqa xabarlar uchun"""
    chat_id = message.chat.id
    
    # Agar foydalanuvchi boshqa holatda bo'lsa
    session = user_sessions.get(chat_id, {})
    
    if session.get('state') == 'code_sent':
        # Kod allaqachon yuborilgan
        username = session.get('username', '')
        session_id = session.get('sessionId')
        
        if session_id and session_id in issued_codes:
            code_data = issued_codes[session_id]
            if code_data['expires_at'] > time.time():
                code = code_data['code']
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(
                    text="📋 KODNI NUSXALASH",
                    callback_data=f"copy_{code}"
                ))
                bot.send_message(
                    chat_id,
                    f"📌 <b>Sizga allaqachon kod yuborilgan!</b>\n\n"
                    f"🔐 Kod: <code>{code}</code>\n\n"
                    f"💡 Kodni saytga kiriting yoki nusxalash uchun tugmani bosing 👇",
                    parse_mode='HTML',
                    reply_markup=markup
                )
                return
    
    # Standart javob
    bot.send_message(
        chat_id,
        "🤖 <b>Buyruqlar:</b>\n\n"
        "• /start — Boshidan boshlash\n"
        "• /mycode — Kodni qayta olish\n"
        "• /help — Yordam",
        parse_mode='HTML'
    )


# ═══════════════════════════════════════════════════════════
# 📋 INLINE KEYBOARD CALLBACK HANDLERLARI
# ═══════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data.startswith('copy_'))
def handle_copy_callback(call):
    """Nusxalash tugmasi"""
    code = call.data.replace('copy_', '')
    chat_id = call.message.chat.id
    
    # Popup xabar (yuqoridan chiqadi)
    bot.answer_callback_query(
        call.id,
        text=f"✅ Kod tayyor!\n\n{code}\n\nEndi saytga kiriting.",
        show_alert=True
    )
    
    # Qo'shimcha xabar — nusxalash uchun qulay
    bot.send_message(
        chat_id,
        f"📋 <b>KODNI NUSXALASH:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<code>{code}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 <b>Qanday nusxalash kerak?</b>\n\n"
        f"1️⃣ Kodni <b>uzun bosing</b>\n"
        f"2️⃣ <b>\"Nusxalash\"</b> ni tanlang\n"
        f"3️⃣ Saytga qo'ying ✅",
        parse_mode='HTML'
    )


@bot.callback_query_handler(func=lambda call: call.data == 'refresh_code')
def handle_refresh_code(call):
    """Kodni qayta olish"""
    chat_id = call.message.chat.id
    session = user_sessions.get(chat_id, {})
    
    if session.get('state') != 'code_sent':
        bot.answer_callback_query(call.id, text="❌ Faol kod yo'q", show_alert=True)
        return
    
    session_id = session.get('sessionId')
    username = session.get('username')
    
    if not session_id or session_id not in pending_registrations:
        bot.answer_callback_query(
            call.id,
            text="❌ Ro'yxatdan o'tish topilmadi. Saytdan qaytadan boshlang.",
            show_alert=True
        )
        return
    
    # Yangi kod yaratish
    new_code = generate_code()
    expires_at = time.time() + CODE_VALIDITY_SECONDS
    
    issued_codes[session_id] = {
        'code': new_code,
        'expires_at': expires_at,
        'chat_id': chat_id,
        'username': username,
        'created_at': time.time()
    }
    
    user_sessions[chat_id]['code'] = new_code
    
    bot.answer_callback_query(call.id, text="✅ Yangi kod yaratildi!")
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(
        text="📋 KODNI NUSXALASH",
        callback_data=f"copy_{new_code}"
    ))
    
    bot.send_message(
        chat_id,
        f"🔄 <b>YANGI KOD YARATILDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔐 Yangi kod:\n\n"
        f"<code>{new_code}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ Amal qilish: <b>{format_time(CODE_VALIDITY_SECONDS)}</b>",
        parse_mode='HTML',
        reply_markup=markup
    )


# ═══════════════════════════════════════════════════════════
# 🌐 FLASK API — SAYT BILAN ALOQA
# ═══════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Server holati"""
    cleanup_expired()
    uptime = int(time.time() - stats["started_at"])
    
    return jsonify({
        "status": "online",
        "service": "Billiard Club Verification API",
        "version": "2.0",
        "uptime_seconds": uptime,
        "uptime_human": f"{uptime//3600}h {(uptime%3600)//60}m",
        "stats": {
            "pending_registrations": len(pending_registrations),
            "active_codes": len(issued_codes),
            "bot_users": len(user_sessions),
            "total_codes_issued": stats["total_codes_issued"]
        }
    })


@app.route('/api/register-pending', methods=['POST'])
def register_pending():
    """
    Sayt yangi ro'yxatdan o'tishni yuboradi
    Body: {sessionId, username, fullName, phone, tablesCount}
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({"ok": False, "error": "JSON kerak"}), 400
        
        session_id = data.get('sessionId')
        username = data.get('username', '').strip()
        full_name = data.get('fullName', '').strip()
        phone = data.get('phone', '').strip()
        tables_count = int(data.get('tablesCount', 3))
        
        # Validatsiya
        if not session_id:
            return jsonify({"ok": False, "error": "sessionId kerak"}), 400
        if not username or len(username) < 3:
            return jsonify({"ok": False, "error": "Username noto'g'ri"}), 400
        if not full_name:
            return jsonify({"ok": False, "error": "FullName kerak"}), 400
        if not phone:
            return jsonify({"ok": False, "error": "Phone kerak"}), 400
        if tables_count < 1 or tables_count > 20:
            return jsonify({"ok": False, "error": "tablesCount 1-20 orasida"}), 400
        
        # Pending registrationni saqlash
        pending_registrations[session_id] = {
            'username': username,
            'fullName': full_name,
            'phone': phone,
            'tablesCount': tables_count,
            'created_at': time.time(),
            'expires_at': time.time() + REGISTRATION_VALIDITY_SECONDS
        }
        
        stats["total_registrations"] += 1
        
        print(f"✅ Yangi pending: {username} ({full_name})")
        
        return jsonify({
            "ok": True,
            "sessionId": session_id,
            "expires_in": REGISTRATION_VALIDITY_SECONDS
        })
    
    except Exception as e:
        print(f"❌ register-pending xatosi: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/check-code', methods=['GET'])
def check_code():
    """
    Sayt kodni tekshiradi (polling)
    Query: ?sessionId=xxx
    """
    try:
        session_id = request.args.get('sessionId')
        
        if not session_id:
            return jsonify({"status": "waiting"})
        
        cleanup_expired()
        
        # Kod tayyormi?
        if session_id in issued_codes:
            code_data = issued_codes[session_id]
            if code_data['expires_at'] > time.time():
                remaining = int(code_data['expires_at'] - time.time())
                return jsonify({
                    "status": "ready",
                    "code": code_data['code'],
                    "expires_in": remaining
                })
            else:
                return jsonify({"status": "expired"})
        
        # Pending registration muddati o'tganmi?
        if session_id in pending_registrations:
            if pending_registrations[session_id].get('expires_at', 0) < time.time():
                return jsonify({"status": "expired"})
            return jsonify({"status": "waiting"})
        
        # Umuman topilmadi
        return jsonify({"status": "not_found"})
    
    except Exception as e:
        print(f"❌ check-code xatosi: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/api/log', methods=['POST'])
def send_log():
    """
    Saytdan Telegram log yuborish
    Body: {message: "HTML message"}
    """
    try:
        data = request.json
        if not data or not data.get('message'):
            return jsonify({"ok": False, "error": "message kerak"}), 400
        
        message = data['message']
        
        # Admin ga yuborish
        try:
            bot.send_message(
                ADMIN_CHAT_ID,
                message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            return jsonify({"ok": True})
        except Exception as e:
            print(f"⚠️ Telegram send xatosi: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500
    
    except Exception as e:
        print(f"❌ log xatosi: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/cleanup', methods=['POST'])
def manual_cleanup():
    """Manual tozalash (cron uchun)"""
    cleaned_codes, cleaned_regs = cleanup_expired()
    return jsonify({
        "ok": True,
        "cleaned_codes": cleaned_codes,
        "cleaned_registrations": cleaned_regs
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Statistika"""
    cleanup_expired()
    return jsonify({
        "ok": True,
        "pending_registrations": len(pending_registrations),
        "active_codes": len(issued_codes),
        "bot_users": len(user_sessions),
        "total_registrations": stats["total_registrations"],
        "total_codes_issued": stats["total_codes_issued"],
        "uptime_seconds": int(time.time() - stats["started_at"])
    })


# ═══════════════════════════════════════════════════════════
# 🧹 AVTOMATIK TOZALASH (har 5 daqiqada)
# ═══════════════════════════════════════════════════════════

def auto_cleanup_worker():
    """Fon vazifasi — muddati o'tganlarni tozalash"""
    while True:
        try:
            time.sleep(300)  # 5 daqiqa
            cleaned_codes, cleaned_regs = cleanup_expired()
            if cleaned_codes > 0 or cleaned_regs > 0:
                print(f"🧹 Tozalandi: {cleaned_codes} kod, {cleaned_regs} registration")
        except Exception as e:
            print(f"⚠️ Cleanup xatosi: {e}")


# ═══════════════════════════════════════════════════════════
# 🚀 ISHGA TUSHIRISH
# ═══════════════════════════════════════════════════════════

def run_bot():
    """Botni polling rejimida ishga tushirish"""
    print("🤖 Bot polling boshlandi...")
    print(f"📱 Bot token: ...{BOT_TOKEN[-10:]}")
    print(f"👤 Admin chat: {ADMIN_CHAT_ID}")
    
    while True:
        try:
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=25,
                none_stop=True
            )
        except Exception as e:
            print(f"⚠️ Bot xatosi: {e}")
            print("🔄 5 soniyadan keyin qayta urinib ko'ramiz...")
            time.sleep(5)


if __name__ == '__main__':
    print("=" * 60)
    print("🎱 BILLIARD CLUB — TELEGRAM VERIFICATION BOT")
    print("=" * 60)
    print()
    
    # Auto cleanup thread
    cleanup_thread = threading.Thread(target=auto_cleanup_worker, daemon=True)
    cleanup_thread.start()
    print("🧹 Auto cleanup: ✅")
    
    # Bot thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print(f"🤖 Bot thread: ✅")
    
    # Server info
    print()
    print("=" * 60)
    print(f"🌐 API Server: http://0.0.0.0:{PORT}")
    print("=" * 60)
    print()
    print("📡 Endpointlar:")
    print(f"   GET  /                          — Status")
    print(f"   POST /api/register-pending      — Yangi registration")
    print(f"   GET  /api/check-code            — Kod tekshirish")
    print(f"   POST /api/log                   — Log yuborish")
    print(f"   GET  /api/stats                 — Statistika")
    print(f"   POST /api/cleanup               — Manual cleanup")
    print()
    print("✅ Tayyor! Sayt bilan ulanishni boshlang.")
    print("=" * 60)
    print()
    
    # Flask serverni ishga tushirish
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False,
        threaded=True
    )
