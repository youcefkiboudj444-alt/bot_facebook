# fb_bot.py — بوت فيسبوك ميسنجر لجيزي (بسيط)
import requests, json, os, logging
from datetime import datetime, timedelta
from flask import Flask, request

# ═══════════ إعدادات فيسبوك ═══════════
FB_APP_ID            = "1868277970865162"
FB_APP_SECRET        = "7b57c221dab53741993c283b0541793e"
FB_VERIFY_TOKEN      = "ed81ef48f38632edce82bcfd09d88636"
FB_PAGE_ACCESS_TOKEN = "EAAajMFzLjAoBS2TFjxhRiiVmdYv7IF3a0ClunCzjf2dRlxND8Wgg8YuxbCiNppzDZBPUMgOJgK3T23MmWV8OlSePvTHlUwepdSzqiOLDpbQ6EP0ZBKnUHqLwJrvaFnV3l7TZC6xx2T3CaP2y9X92Py8x1PJsCLZA59DYMaZCIKyzU7lcZABJXujj1ew93doUIB8wpYj4T8wwZDZD"
FB_API_URL           = "https://graph.facebook.com/v18.0/me/messages"

# ═══════════ إعدادات جيزي ═══════════
CLIENT_ID     = "87pIExRhxBb3_wGsA5eSEfyATloa"
CLIENT_SECRET = "uf82p68Bgisp8Yg1Uz8Pf6_v1XYa"
BASE_URL      = "https://apim.djezzy.dz"

PROXY_URL = "http://VOdU7NxiOv20_custom_zone_DZ_st__city_sid_23611181_time_90:3149931@change6.owlproxy.com:7778"
PROXIES   = {"http": PROXY_URL, "https": PROXY_URL}

HEADERS = {
    "User-Agent": "MobileApp/3.0.4",
    "accept-language": "fr",
    "Content-Type": "application/json",
    "Accept": "application/json"
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

# ═══════════ دوال جيزي ═══════════
def clean_phone(raw: str) -> str | None:
    p = raw.strip().replace(" ", "").replace("-", "").replace(".", "")
    if p.startswith("+213"): p = "213" + p[4:]
    elif p.startswith("00213"): p = "213" + p[5:]
    elif p.startswith("213") and len(p) == 12: pass
    elif p.startswith("0") and len(p) == 10: p = "213" + p[1:]
    elif len(p) == 9 and p.startswith("7"): p = "213" + p
    else: return None
    if not (len(p) == 12 and p.isdigit() and p.startswith("213")): return None
    return p

def fmt_phone(msisdn: str) -> str:
    return "0" + msisdn[3:] if msisdn.startswith("213") else msisdn

def send_otp(msisdn: str) -> tuple[int, str]:
    url = f"{BASE_URL}/mobile-api/oauth2/registration"
    params = {"msisdn": msisdn, "client_id": CLIENT_ID, "scope": "smsotp"}
    body = {"consent-agreement": [{"marketing-notifications": False}], "is-consent": True}
    try:
        r = requests.post(url, params=params, json=body, headers=HEADERS, proxies=PROXIES, timeout=15)
        log.info(f"send_otp [{r.status_code}]: {r.text[:200]}")
        return r.status_code, r.text
    except Exception as e:
        log.error(f"send_otp: {e}")
        return 500, str(e)

def verify_otp(msisdn: str, otp: str) -> tuple[dict | None, int]:
    url = f"{BASE_URL}/mobile-api/oauth2/token"
    headers = {**HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
    data = (f"otp={otp}&mobileNumber={msisdn}&scope=djezzyAppV2"
            f"&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=mobile")
    try:
        r = requests.post(url, data=data, headers=headers, proxies=PROXIES, timeout=15)
        return r.json(), r.status_code
    except Exception as e:
        log.error(f"verify_otp: {e}")
        return None, 500

def djezzy_api(method: str, endpoint: str, token: str, body: dict = None) -> tuple[dict | None, int]:
    url = f"{BASE_URL}/mobile-api/api/v1/{endpoint}"
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, proxies=PROXIES, timeout=15)
        else:
            r = requests.post(url, headers=headers, json=body, proxies=PROXIES, timeout=15)
        log.info(f"API {method} {endpoint} [{r.status_code}]: {r.text[:200]}")
        return r.json(), r.status_code
    except Exception as e:
        log.error(f"djezzy_api: {e}")
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

# ═══════════ منطق البوت ═══════════
def handle_message(psid: str, text: str):
    text = text.strip()
    user = get_user(psid)
    state = user_states.get(psid, "menu" if user.get("accounts") else "phone")

    # ═════ تسجيل الدخول ═════
    if not user.get("accounts"):
        if state == "phone":
            msisdn = clean_phone(text)
            if not msisdn:
                send_fb(psid, "⚠️ رقم خاطئ.\nأدخل رقم جيزي مثل: 0770123456")
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
            if not (text.isdigit() and len(text) == 6):
                send_fb(psid, "⚠️ أدخل 6 أرقام فقط.")
                return
            msisdn = temp_data.get(psid, {}).get("msisdn", "")
            result, code = verify_otp(msisdn, text)
            if code == 200 and result and "access_token" in result:
                save_account(psid, msisdn, result["access_token"], result.get("refresh_token", ""))
                user_states[psid] = "menu"
                send_fb(psid, f"🎉 تم تسجيل الدخول!\n📱 {fmt_phone(msisdn)}\n\n" + main_menu())
            else:
                send_fb(psid, "❌ الرمز خاطئ. أرسل /start")
            return

        user_states[psid] = "phone"
        send_fb(psid, "👋 أهلاً بك في بوت جيزي!\n\n📱 أدخل رقم هاتفك (07XXXXXXXX):")
        return

    # ═════ مستخدم مسجّل ═════
    msisdn = user["active"]
    if not msisdn:
        send_fb(psid, "❌ لا يوجد حساب نشط. أرسل /start")
        return
    token = user["accounts"][msisdn]["token"]

    # ── الرجوع للقائمة ──
    if text in ("0", "/menu", "قائمة", "/start", "رجوع"):
        user_states[psid] = "menu"
        send_fb(psid, main_menu())
        return

    # ── 1: الهدية الأسبوعية ──
    if text == "1":
        rem = get_remaining(psid, msisdn, "GIFT", GIFT_DURATION_H)
        if rem:
            send_fb(psid, f"⏳ الهدية نشطة بالفعل.\n⏱️ المتبقي: {rem}\n\n" + main_menu())
            return
        send_fb(psid, "⏳ جاري تفعيل الهدية...")
        res, code = djezzy_api("POST", f"subscribers/activate-product/{msisdn}", token,
                               {"packageCode": "GIFTWALKWIN2GO"})
        if code in (200, 201):
            save_activation(psid, msisdn, "GIFT")
            rem = get_remaining(psid, msisdn, "GIFT", GIFT_DURATION_H)
            send_fb(psid, f"🎁 تم تفعيل الهدية الأسبوعية!\n"
                          f"📦 2GB لمدة 7 أيام\n"
                          f"⏱️ المتبقي: {rem}\n\n" + main_menu())
        elif code == 401:
            send_fb(psid, "🔑 انتهت الجلسة. أرسل /start لتسجيل الدخول مجدداً.")
        else:
            msg = extract_msg(res) or "فشل التفعيل"
            send_fb(psid, f"⚠️ {msg}\n\n" + main_menu())
        return

    # ── 2: عرض العروض ──
    if text == "2":
        user_states[psid] = "offers"
        send_fb(psid, offers_menu())
        return

    if user_states.get(psid) == "offers":
        if text not in OFFERS:
            send_fb(psid, "⚠️ رقم غير صحيح. أرسل رقم عرض من القائمة أو 0 للرجوع.")
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
        if text == "1":
            offer_key = temp_data.get(psid, {}).get("offer")
            if not offer_key or offer_key not in OFFERS:
                user_states[psid] = "menu"
                send_fb(psid, main_menu())
                return
            pkg, name, dur = OFFERS[offer_key]
            send_fb(psid, f"⏳ جاري تفعيل {name}...")
            res, code = djezzy_api("POST", f"subscribers/activate-product/{msisdn}", token,
                                   {"packageCode": pkg})
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
    if text == "3":
        res, code = djezzy_api("GET", f"subscribers/main-balance/{msisdn}", token)
        if code == 200 and res:
            d = res.get("data", res)
            bal = d.get("mainBalance", "0.0")
            due = d.get("due", 0)
            send_fb(psid, f"💰 الرصيد المالي\n──────────────\n"
                          f"💵 الرصيد: {bal} دج\n"
                          f"📋 المستحق: {due} دج\n\n" + main_menu())
        elif code == 401:
            send_fb(psid, "🔑 انتهت الجلسة. أرسل /start")
        else:
            send_fb(psid, "❌ تعذّر جلب الرصيد.\n\n" + main_menu())
        return

    # ── 6: تواصل على تيليجرام ──
    if text == "6":
        send_fb(psid,
            "📢 تواصل معنا\n"
            "──────────────────\n"
            "انضم لقناتنا على تيليجرام للحصول على آخر العروض والتحديثات:\n\n"
            f"👉 {TELEGRAM_CHANNEL}\n\n" + main_menu())
        return

    send_fb(psid, "🤖 لم أفهم طلبك.\n\n" + main_menu())


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