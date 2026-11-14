# main.py — بوت فيسبوك ميسنجر لجيزي (عبر السيرفر الوسيط - نسخة احترافية)
import requests, json, os, logging
from datetime import datetime, timedelta
from flask import Flask, request

# ═══════════ إعدادات فيسبوك ═══════════
FB_APP_ID            = "1868277970865162"
FB_APP_SECRET        = "7b57c221dab53741993c283b0541793e"
FB_VERIFY_TOKEN      = "ed81ef48f38632edce82bcfd09d88636"
FB_PAGE_ACCESS_TOKEN = "EAAajMFzLjAoBS2TFjxhRiiVmdYv7IF3a0ClunCzjf2dRlxND8Wgg8YuxbCiNppzDZBPUMgOJgK3T23MmWV8OlSePvTHlUwepdSzqiOLDpbQ6EP0ZBKnUHqLwJrvaFnV3l7TZC6xx2T3CaP2y9X92Py8x1PJsCLZA59DYMaZCIKyzU7lcZABJXujj1ew93doUIB8wpYj4T8wwZDZD"
FB_API_URL           = "https://graph.facebook.com/v18.0/me/messages"

# ═══════════ إعدادات API الوسيط (الجديد) ═══════════
DJEZZY_API_URL = "http://78.154.103.31:14442/v1/djezzy"
DJEZZY_API_KEY = "dz_CB1KWTTDOCdHsoSjbkyR1DK9DeabAZUJxvOehmWw"

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": DJEZZY_API_KEY
}

SESSIONS_FILE = "fb_sessions.json"
GIFT_DURATION_H = 7 * 24
TELEGRAM_CHANNEL = "https://t.me/tasjil_internet_algeria"

# ═══════════ العروض ═══════════
OFFERS = {
    "1": ("DOVINTSPEEDDAY100MoPRE",    "📶 300 MO يومية",       24),
    "2": ("BTLINTSPEEDDAY2Go",         "🌐 2GB يومية",           24),
    "3": ("DOVINTSPEEDDAY5GoPRE5G",    "⚡ IMTYAZE 5GB يومية",   24),
    "4": ("DOVINTSPEEDWEEK2GoPRE",     "🚀 4GB أسبوعية",         7*24),
    "5": ("DOVINTSPEEDWEEK3GoPRE",     "💎 10GB أسبوعية",        7*24),
    "6": ("DOVINTSPEEDMONTH30GoPRE",   "🔥 30GB شهرية",          30*24),
    "7": ("DOVINTSPEEDMONTH100GoPRE5G","👑 100GB شهرية 5G",      30*24),
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)
user_states: dict[str, str] = {}
temp_data: dict[str, dict] = {}

# ═══════════ تخزين ═══════════
def load_sessions() -> dict:
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_sessions(data: dict):
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(psid: str) -> dict:
    data = load_sessions()
    if psid not in data:
        data[psid] = {"accounts": {}, "active": None}
        save_sessions(data)
    return data[psid]

def save_account(psid: str, msisdn: str, token: str, rtoken: str = ""):
    data = load_sessions()
    if psid not in data:
        data[psid] = {"accounts": {}, "active": None}
    if msisdn not in data[psid]["accounts"]:
        data[psid]["accounts"][msisdn] = {"token": token, "refresh_token": rtoken, "activations": {}}
    else:
        data[psid]["accounts"][msisdn]["token"] = token
        if rtoken:
            data[psid]["accounts"][msisdn]["refresh_token"] = rtoken
    data[psid]["active"] = msisdn
    save_sessions(data)

def save_activation(psid: str, msisdn: str, key: str):
    data = load_sessions()
    if psid in data and msisdn in data[psid]["accounts"]:
        acts = data[psid]["accounts"][msisdn].setdefault("activations", {})
        acts[key] = datetime.utcnow().isoformat()
        save_sessions(data)

def get_remaining(psid: str, msisdn: str, key: str, dur_h: int) -> str | None:
    try:
        data = load_sessions()
        acts = data[psid]["accounts"][msisdn].get("activations", {})
        ts = acts.get(key)
        if not ts:
            return None
        expires = datetime.fromisoformat(ts) + timedelta(hours=dur_h)
        rem = expires - datetime.utcnow()
        if rem.total_seconds() <= 0:
            return None
        mins = int(rem.total_seconds() // 60)
        h, m = divmod(mins, 60)
        d, h = divmod(h, 24)
        parts = []
        if d: parts.append(f"{d} يوم")
        if h: parts.append(f"{h} ساعة")
        if m: parts.append(f"{m} دقيقة")
        return " و ".join(parts) or "أقل من دقيقة"
    except Exception:
        return None

# ═══════════ دوال مساعدة ═══════════
def clean_phone(raw: str) -> str | None:
    p = raw.strip().replace(" ", "").replace("-", "").replace(".", "")
    if p.startswith("+213"): p = "213" + p[4:]
    elif p.startswith("00213"): p = "213" + p[5:]
    elif p.startswith("213") and len(p) == 12: pass
    elif p.startswith("0") and len(p) == 10: p = "213" + p[1:]
    elif len(p) == 9 and p.startswith("7"): p = "213" + p
    else: return None
    if not (len(p) == 12 and p.isdigit() and p.startswith("213")): return None
    # الـ API الوسيط يطلب الرقم بصيغة 07XXXXXXXX (10 أرقام)
    return "0" + p[3:]

def fmt_phone(msisdn: str) -> str:
    return msisdn

# ═══════════ دوال API الوسيط الجديد ═══════════
def send_otp(phone: str) -> tuple[int, str]:
    try:
        r = requests.post(f"{DJEZZY_API_URL}/otp/send", headers=HEADERS, json={"phone": phone}, timeout=20)
        log.info(f"send_otp [{r.status_code}]: {r.text[:200]}")
        return r.status_code, r.text
    except Exception as e:
        log.error(f"send_otp: {e}")
        return 500, str(e)

def verify_otp(phone: str, otp: str) -> tuple[dict | None, int]:
    try:
        r = requests.post(f"{DJEZZY_API_URL}/otp/verify", headers=HEADERS, json={"phone": phone, "otp": otp}, timeout=20)
        log.info(f"verify_otp [{r.status_code}]: {r.text[:200]}")
        return r.json(), r.status_code
    except Exception as e:
        log.error(f"verify_otp: {e}")
        return None, 500

def api_balance(phone: str) -> tuple[dict | None, int]:
    try:
        r = requests.get(f"{DJEZZY_API_URL}/balance?phone={phone}", headers=HEADERS, timeout=20)
        return r.json(), r.status_code
    except Exception as e:
        log.error(f"api_balance: {e}")
        return None, 500

def api_activate(phone: str, package_code: str) -> tuple[dict | None, int]:
    try:
        body = {"phone": phone, "package_code": package_code}
        r = requests.post(f"{DJEZZY_API_URL}/activate", headers=HEADERS, json=body, timeout=20)
        return r.json(), r.status_code
    except Exception as e:
        log.error(f"api_activate: {e}")
        return None, 500

def extract_msg(res, default=""):
    if not res: return default
    m = res.get("message", default)
    if isinstance(m, dict): return m.get("ar") or m.get("en") or default
    return str(m) if m else default

# ═══════════ إرسال رسالة فيسبوك ═══════════
def send_fb(psid: str, text: str):
    try:
        r = requests.post(
            FB_API_URL,
            params={"access_token": FB_PAGE_ACCESS_TOKEN},
            json={"recipient": {"id": psid}, "message": {"text": text}},
            timeout=15
        )
        if r.status_code != 200:
            log.warning(f"send_fb [{r.status_code}]: {r.text[:200]}")
    except Exception as e:
        log.error(f"send_fb: {e}")

# ═══════════ القوائم النصية ═══════════
def main_menu() -> str:
    return (
        "🏠 القائمة الرئيسية\n"
        "──────────────────\n"
        "1️⃣ تفعيل الهدية الأسبوعية (2GB)\n"
        "2️⃣ عرض العروض\n"
        "3️⃣ الرصيد المالي\n"
        "6️⃣ تواصل معنا على تيليجرام\n\n"
        "أرسل الرقم المطلوب:"
    )

def offers_menu() -> str:
    txt = "🏷️ العروض المتاحة\n──────────────────\n"
    for k, (_, name, _) in OFFERS.items():
        txt += f"{k}️⃣ {name}\n"
    txt += "\nأرسل رقم العرض للتفعيل\n0️⃣ للرجوع"
    return txt

# ═══════════ الردود الذكية (Smart Fallback) ═══════════
def smart_reply(text: str, is_logged_in: bool) -> str | None:
    t = text.lower().strip()
    
    greetings = ["سلام", "صحا", "صباح", "مساء", "مرحبا", "أهلا", "اهلا", "هاي", "hello", "hi", "bonjour", "salam"]
    if any(w in t for w in greetings):
        return "👋 أهلاً بك! كيف يمكنني مساعدتك اليوم؟\n(اختر من القائمة أدناه 👇)" if is_logged_in else "👋 أهلاً بك في بوت جيزي!\n\n📱 يرجى إدخال رقم هاتفك (07XXXXXXXX) للبدء:"

    thanks = ["شكرا", "مشكور", "يعطيك", "بارك الله", "merci", "thanks", "thx"]
    if any(w in t for w in thanks):
        return "🌹 على الرحب والسعة! نحن دائماً في خدمتك.\nإذا احتجت أي شيء آخر، اختر من القائمة." if is_logged_in else "🌹 على الرحب والسعة! يرجى إدخال رقم هاتفك للبدء:"

    who = ["شكون", "من راك", "من أنت", "واش راك", "كيف حالك", "كيفك", "واش هذا", "بوت", "بوت واش يدير"]
    if any(w in t for w in who):
        return "🤖 أنا بوت جيزي الذكي!\nأقوم بتفعيل الهدية الأسبوعية، عرض الرصيد، وتفعيل العروض بضغطة زر.\n" + (main_menu() if is_logged_in else "📱 يرجى إدخال رقم هاتفك للبدء:")

    help_words = ["مساعدة", "مساعده", "كيفاش", "كيف", "شرح", "help", "aide", "واش ندير"]
    if any(w in t for w in help_words):
        if is_logged_in: return "❓ كيف يمكنني مساعدتك؟\n\n" + main_menu()
        else: return "❓ للبدء، يرجى إدخال رقم هاتفك (07XXXXXXXX)\n\nمثال: 0770123456"

    gift_words = ["هدية", "هديه", "مجانا", "مجاني", "gift", "2gb", "2 go"]
    if any(w in t for w in gift_words):
        if is_logged_in: return "🎁 لتفعيل الهدية الأسبوعية (2GB مجاناً)، أرسل الرقم: 1"
        else: return "🎁 لتفعيل الهدية، يجب تسجيل الدخول أولاً.\n📱 أدخل رقم هاتفك:"

    offer_words = ["عرض", "عروض", "باقة", "باقات", "انترنت", "أنترنت", "نت", "جيجا", "go", "gb", "offer", "forfait"]
    if any(w in t for w in offer_words):
        if is_logged_in: return "🏷️ لعرض الباقات المتاحة، أرسل الرقم: 2"
        else: return "📱 لتسجيل الدخول وعرض الباقات، يرجى إدخال رقم هاتفك:"

    balance_words = ["رصيد", "فلوس", "دراهم", "solde", "balance", "credit", "كارت"]
    if any(w in t for w in balance_words):
        if is_logged_in: return "💰 لمعرفة رصيدك المالي، أرسل الرقم: 3"
        else: return "📱 لتسجيل الدخول وعرض رصيدك، يرجى إدخال رقم هاتفك:"

    if is_logged_in: return "🤖 لم أفهم قصدك تماماً، لكنني هنا لمساعدتك!\nيرجى اختيار أحد الخيارات من القائمة أدناه 👇\n\n" + main_menu()
    else: return "🤖 يرجى إدخال رقم هاتفك (07XXXXXXXX) لنتمكن من مساعدتك في تسجيل الدخول:"

# ═══════════ منطق البوت ═══════════
def handle_message(psid: str, text: str):
    text = text.strip()
    user = get_user(psid)
    state = user_states.get(psid, "menu" if user.get("accounts") else "phone")

    # ═════ حالة: غير مسجل (تسجيل الدخول) ═════
    if not user.get("accounts"):
        if state == "phone":
            msisdn = clean_phone(text)
            if not msisdn:
                reply = smart_reply(text, is_logged_in=False)
                send_fb(psid, reply)
                return
            temp_data[psid] = {"msisdn": msisdn}
            code, _ = send_otp(msisdn)
            
            if code in (200, 201):
                user_states[psid] = "otp"
                send_fb(psid, f"✅ تم إرسال الرمز إلى {fmt_phone(msisdn)}\n\nأدخل رمز OTP (6 أرقام):")
            elif code == 400:
                send_fb(psid, "❌ الرقم غير مسجل في جيزي. جرب رقماً آخر:")
            elif code == 429:
                send_fb(psid, "⚠️ كثرة المحاولات، انتظر دقيقة.")
            else:
                send_fb(psid, "❌ فشل الإرسال، حاول لاحقاً.")
            return

        if state == "otp":
    # إضافة: إذا أراد المستخدم الإلغاء أو البدء من جديد
    if text.lower() in ("/start", "الغاء", "إلغاء", "بدء"):
        user_states[psid] = "phone"
        send_fb(psid, "🔄 تم الإلغاء.\n\n📱 يرجى إدخال رقم هاتفك (07XXXXXXXX):")
        return
        
    if not (text.isdigit() and len(text) == 6):
        send_fb(psid, "⚠️ أدخل رمزاً مكوناً من 6 أرقام فقط (الذي وصلك في SMS).")
        return
            msisdn = temp_data.get(psid, {}).get("msisdn", "")
            result, code = verify_otp(msisdn, text)
            
            if code == 200 and result and result.get("ok"):
                token = result.get("token") or result.get("access_token") or "session_active"
                rtoken = result.get("refresh_token", "")
                save_account(psid, msisdn, token, rtoken)
                user_states[psid] = "menu"
                send_fb(psid, f"🎉 تم تسجيل الدخول بنجاح!\n📱 {fmt_phone(msisdn)}\n\n" + main_menu())
            else:
                send_fb(psid, "❌ الرمز خاطئ أو منتهي الصلاحية. أرسل /start للمحاولة مجدداً.")
            return

        user_states[psid] = "phone"
        send_fb(psid, "👋 أهلاً بك في بوت جيزي الاحترافي!\n\n📱 أدخل رقم هاتفك (07XXXXXXXX):")
        return

    # ═════ حالة: مسجل دخول (القائمة الرئيسية) ═════
    msisdn = user["active"]
    if not msisdn:
        send_fb(psid, "❌ لا يوجد حساب نشط. أرسل /start")
        return

    # ── الرجوع للقائمة ──
    if text in ("0", "/menu", "قائمة", "/start", "رجوع", "الرجوع", "رجع"):
        user_states[psid] = "menu"
        send_fb(psid, main_menu())
        return

    # ── 1: الهدية الأسبوعية ──
    if text in ("1", "1️⃣"):
        rem = get_remaining(psid, msisdn, "GIFT", GIFT_DURATION_H)
        if rem:
            send_fb(psid, f"⏳ الهدية نشطة بالفعل.\n⏱️ المتبقي: {rem}\n\n" + main_menu())
            return
        send_fb(psid, "⏳ جاري تفعيل الهدية...")
        res, code = api_activate(msisdn, "GIFTWALKWIN2GO")
        
        if code in (200, 201):
            save_activation(psid, msisdn, "GIFT")
            rem = get_remaining(psid, msisdn, "GIFT", GIFT_DURATION_H)
            send_fb(psid, f"🎁 تم تفعيل الهدية الأسبوعية!\n"
                          f"📦 2GB لمدة 7 أيام\n"
                          f"⏱️ المتبقي: {rem}\n\n" + main_menu())
        else:
            msg = extract_msg(res) or "فشل التفعيل"
            send_fb(psid, f"⚠️ {msg}\n\n" + main_menu())
        return

    # ── 2: عرض العروض ──
    if text in ("2", "2️⃣"):
        user_states[psid] = "offers"
        send_fb(psid, offers_menu())
        return

    if user_states.get(psid) == "offers":
        if text not in OFFERS and text not in ("0", "0️⃣", "رجوع"):
            reply = smart_reply(text, is_logged_in=True)
            send_fb(psid, reply)
            return
        if text in ("0", "0️⃣", "رجوع"):
            user_states[psid] = "menu"
            send_fb(psid, main_menu())
            return
        pkg, name, dur = OFFERS[text]
        rem = get_remaining(psid, msisdn, text, dur)
        if rem:
            send_fb(psid, f"✅ {name} نشط حالياً\n⏱️ المتبقي: {rem}\n\n" + main_menu())
            user_states[psid] = "menu"
            return
        temp_data.setdefault(psid, {})["offer"] = text
        user_states[psid] = "offer_confirm"
        send_fb(psid, f"🏷️ {name}\n\nهل تريد التفعيل؟\n1️⃣ نعم\n0️⃣ لا / رجوع")
        return

    if user_states.get(psid) == "offer_confirm":
        if text in ("1", "1️⃣", "نعم"):
            offer_key = temp_data.get(psid, {}).get("offer")
            if not offer_key or offer_key not in OFFERS:
                user_states[psid] = "menu"
                send_fb(psid, main_menu())
                return
            pkg, name, dur = OFFERS[offer_key]
            send_fb(psid, f"⏳ جاري تفعيل {name}...")
            res, code = api_activate(msisdn, pkg)
            
            if code in (200, 201):
                save_activation(psid, msisdn, offer_key)
                rem = get_remaining(psid, msisdn, offer_key, dur)
                send_fb(psid, f"🎉 تم تفعيل {name}!\n⏱️ المتبقي: {rem}\n\n" + main_menu())
            elif code == 402:
                send_fb(psid, f"❌ رصيدك غير كافٍ لتفعيل {name}.\n\n" + main_menu())
            else:
                send_fb(psid, f"⚠️ {extract_msg(res) or 'فشل التفعيل'}\n\n" + main_menu())
        else:
            send_fb(psid, main_menu())
        user_states[psid] = "menu"
        return

    # ── 3: الرصيد المالي ──
    if text in ("3", "3️⃣"):
        res, code = api_balance(msisdn)
        if code == 200 and res:
            bal = res.get("balance", res.get("mainBalance", "0.0"))
            send_fb(psid, f"💰 الرصيد المالي\n──────────────\n"
                          f"💵 الرصيد: {bal} دج\n\n" + main_menu())
        else:
            send_fb(psid, "❌ تعذّر جلب الرصيد.\n\n" + main_menu())
        return

    # ── 6: تواصل على تيليجرام ──
    if text in ("6", "6️⃣"):
        send_fb(psid,
            "📢 تواصل معنا\n"
            "──────────────────\n"
            "انضم لقناتنا على تيليجرام للحصول على آخر العروض والتحديثات:\n\n"
            f"👉 {TELEGRAM_CHANNEL}\n\n" + main_menu())
        return

    reply = smart_reply(text, is_logged_in=True)
    send_fb(psid, reply)


# ═══════════ Webhook ═══════════
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge", ""), 200
    return "Invalid", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            psid = event["sender"]["id"]
            if "message" in event and "text" in event["message"]:
                try:
                    handle_message(psid, event["message"]["text"])
                except Exception as e:
                    log.error(f"handle_message error: {e}")
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "Djezzy FB Bot is running ✅", 200
