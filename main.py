import os
import json
import uuid
import base64
import asyncio
import secrets
import subprocess
import signal
from pathlib import Path
from datetime import datetime, timedelta
from aiohttp import web, WSMsgType, ClientSession, ClientWebSocketResponse
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "mellfreezy")
BASE_URL = os.getenv("BASE_URL", "https://nefritvpn.onrender.com")
PORT = int(os.getenv("PORT", 8080))
XRAY_PORT = 10001

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "vpn.db"
XRAY_CONFIG_PATH = DATA_DIR / "xray_config.json"

SUPPORT_USERNAME = "mellfreezy"
CHANNEL_USERNAME = "nefrit_vpn"

xray_process = None


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                username TEXT,
                user_uuid TEXT UNIQUE,
                path TEXT UNIQUE,
                key_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                days INTEGER,
                is_used BOOLEAN DEFAULT 0,
                used_by INTEGER,
                used_by_username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activated_at TIMESTAMP,
                expires_at TIMESTAMP,
                is_revoked BOOLEAN DEFAULT 0
            )
        ''')
        await db.commit()


async def create_key(days=None):
    key = "NEFRIT-" + secrets.token_hex(8).upper()
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO keys (key, days, created_at) VALUES (?, ?, ?)",
            (key, days, now)
        )
        await db.commit()
        cursor = await db.execute("SELECT id FROM keys WHERE key = ?", (key,))
        row = await cursor.fetchone()
        key_id = row[0] if row else 0
    return key, key_id


async def get_key_info(key_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, key, days, is_used, used_by_username, expires_at, is_revoked FROM keys WHERE id = ?",
            (key_id,)
        )
        return await cursor.fetchone()


async def revoke_key(key_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE keys SET is_revoked = 1 WHERE id = ?", (key_id,))
        await db.execute("UPDATE users SET is_active = 0 WHERE key_id = ?", (key_id,))
        await db.commit()
    await restart_xray()


async def check_expired_users():
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_active = 0 WHERE expires_at IS NOT NULL AND expires_at < ? AND is_active = 1",
            (now,)
        )
        await db.commit()


async def get_all_users():
    await check_expired_users()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_uuid, path FROM users WHERE is_active = 1")
        return await cursor.fetchall()


async def activate_key(key, user_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, is_used, days, is_revoked FROM keys WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()

        if not row:
            return None, "Ключ не найден"

        key_id = row[0]
        is_used = row[1]
        days = row[2]
        is_revoked = row[3]

        if is_revoked:
            return None, "Ключ аннулирован"
        if is_used:
            return None, "Ключ уже использован"

        cursor = await db.execute("SELECT path FROM users WHERE user_id = ?", (user_id,))
        existing = await cursor.fetchone()
        if existing:
            return existing[0], None

        user_uuid = str(uuid.uuid4())
        user_path = "u" + str(user_id)

        now = datetime.now()
        if days:
            expires_at = (now + timedelta(days=days)).isoformat()
        else:
            expires_at = None

        await db.execute(
            "INSERT INTO users (user_id, username, user_uuid, path, key_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, user_uuid, user_path, key_id, now.isoformat(), expires_at)
        )
        await db.execute(
            "UPDATE keys SET is_used = 1, used_by = ?, used_by_username = ?, activated_at = ?, expires_at = ? WHERE key = ?",
            (user_id, username, now.isoformat(), expires_at, key)
        )
        await db.commit()

        await restart_xray()
        return user_path, None


async def get_user_info(user_id):
    await check_expired_users()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT path, user_uuid, is_active, expires_at FROM users WHERE user_id = ?",
            (user_id,)
        )
        return await cursor.fetchone()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        active = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM keys WHERE is_used = 0 AND is_revoked = 0")
        free_keys = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM keys")
        total_keys = (await cursor.fetchone())[0]
        return active, total, free_keys, total_keys


async def get_keys_list():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, key, days, is_used, used_by_username, expires_at, is_revoked FROM keys ORDER BY id DESC LIMIT 20"
        )
        return await cursor.fetchall()


async def generate_xray_config():
    users = await get_all_users()

    clients = []
    for user_uuid, path in users:
        clients.append({"id": user_uuid, "level": 0})

    if not clients:
        clients.append({"id": str(uuid.uuid4()), "level": 0})

    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": XRAY_PORT,
            "listen": "127.0.0.1",
            "protocol": "vless",
            "settings": {"clients": clients, "decryption": "none"},
            "streamSettings": {"network": "ws", "wsSettings": {"path": "/tunnel"}}
        }],
        "outbounds": [{"protocol": "freedom", "tag": "direct"}],
        "dns": {"servers": ["8.8.8.8", "1.1.1.1"]}
    }

    with open(XRAY_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print("Xray config saved: " + str(len(clients)) + " clients")


def start_xray():
    global xray_process

    if not XRAY_CONFIG_PATH.exists():
        print("Xray config not found!")
        return False

    try:
        xray_process = subprocess.Popen(
            ["/usr/local/bin/xray", "run", "-config", str(XRAY_CONFIG_PATH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("Xray started, PID: " + str(xray_process.pid))
        return True
    except Exception as e:
        print("Failed to start Xray: " + str(e))
        return False


def stop_xray():
    global xray_process
    if xray_process:
        xray_process.terminate()
        xray_process.wait()
        xray_process = None
        print("Xray stopped")


async def restart_xray():
    stop_xray()
    await generate_xray_config()
    await asyncio.sleep(1)
    start_xray()
    await asyncio.sleep(2)


def generate_vless_link(user_uuid, user_path):
    host = BASE_URL.replace("https://", "").replace("http://", "")
    link = "vless://" + user_uuid + "@" + host + ":443"
    link = link + "?encryption=none&security=tls&type=ws"
    link = link + "&host=" + host + "&path=%2Ftunnel"
    link = link + "#Nefrit-" + user_path
    return link


def generate_subscription(user_uuid, user_path):
    link = generate_vless_link(user_uuid, user_path)
    return base64.b64encode(link.encode()).decode()


async def handle_index(request):
    return web.Response(text="<h1>Nefrit VPN Active</h1>", content_type="text/html")


async def handle_health(request):
    xray_running = xray_process is not None and xray_process.poll() is None
    return web.json_response({"status": "ok", "xray": xray_running})


async def handle_subscription(request):
    path = request.match_info["path"]
    await check_expired_users()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_uuid, is_active, expires_at FROM users WHERE path = ?",
            (path,)
        )
        row = await cursor.fetchone()

    if not row:
        return web.Response(text="Not found", status=404)

    user_uuid = row[0]
    is_active = row[1]
    expires_at = row[2]

    if not is_active:
        return web.Response(text="Subscription expired", status=403)

    if expires_at:
        exp = datetime.fromisoformat(expires_at)
        if exp <= datetime.now():
            return web.Response(text="Subscription expired", status=403)

    sub = generate_subscription(user_uuid, path)
    return web.Response(text=sub, content_type="text/plain", headers={"Profile-Update-Interval": "6"})


async def handle_tunnel(request):
    if request.headers.get("Upgrade", "").lower() != "websocket":
        return web.Response(text="WebSocket required", status=400)

    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)

    print("New WS connection from " + str(request.remote))

    try:
        url = "http://127.0.0.1:" + str(XRAY_PORT) + "/tunnel"
        async with ClientSession() as session:
            async with session.ws_connect(url, timeout=30) as ws_xray:

                async def client_to_xray():
                    try:
                        async for msg in ws_client:
                            if msg.type == WSMsgType.BINARY:
                                await ws_xray.send_bytes(msg.data)
                            elif msg.type == WSMsgType.TEXT:
                                await ws_xray.send_str(msg.data)
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                                break
                    except Exception as e:
                        print("client_to_xray error: " + str(e))

                async def xray_to_client():
                    try:
                        async for msg in ws_xray:
                            if msg.type == WSMsgType.BINARY:
                                await ws_client.send_bytes(msg.data)
                            elif msg.type == WSMsgType.TEXT:
                                await ws_client.send_str(msg.data)
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                                break
                    except Exception as e:
                        print("xray_to_client error: " + str(e))

                await asyncio.gather(client_to_xray(), xray_to_client(), return_exceptions=True)

    except Exception as e:
        print("Tunnel error: " + str(e))
    finally:
        if not ws_client.closed:
            await ws_client.close()
        print("WS connection closed")

    return ws_client


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class States(StatesGroup):
    waiting_key = State()
    waiting_days = State()
    waiting_revoke_id = State()


def is_admin(user):
    if user.username:
        return user.username.lower() == ADMIN_USERNAME.lower()
    return False


def main_kb(admin=False):
    buttons = [
        [InlineKeyboardButton(text="Aktivirovat", callback_data="activate")],
        [InlineKeyboardButton(text="Moya podpiska", callback_data="mysub")],
        [
            InlineKeyboardButton(text="Podderzhka", url="https://t.me/" + SUPPORT_USERNAME),
            InlineKeyboardButton(text="Kanal", url="https://t.me/" + CHANNEL_USERNAME)
        ]
    ]
    if admin:
        buttons.append([InlineKeyboardButton(text="Admin", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sozdat kluch", callback_data="newkey")],
        [InlineKeyboardButton(text="Spisok kluchey", callback_data="keys")],
        [InlineKeyboardButton(text="Annulirovat kluch", callback_data="revoke")],
        [InlineKeyboardButton(text="Statistika", callback_data="stats")],
        [InlineKeyboardButton(text="Restart Xray", callback_data="restart_xray")],
        [InlineKeyboardButton(text="Nazad", callback_data="back")]
    ])


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Menu", callback_data="back")]
    ])


def back_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Admin", callback_data="admin")]
    ])


def days_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7", callback_data="days_7"),
            InlineKeyboardButton(text="14", callback_data="days_14"),
            InlineKeyboardButton(text="30", callback_data="days_30")
        ],
        [
            InlineKeyboardButton(text="60", callback_data="days_60"),
            InlineKeyboardButton(text="90", callback_data="days_90"),
            InlineKeyboardButton(text="180", callback_data="days_180")
        ],
        [InlineKeyboardButton(text="365", callback_data="days_365")],
        [InlineKeyboardButton(text="Bessrochno", callback_data="days_0")],
        [InlineKeyboardButton(text="Otmena", callback_data="admin")]
    ])


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Otmena", callback_data="back")]
    ])


def format_expiry(expires_at, is_revoked):
    if is_revoked:
        return "Annulirovan"
    if not expires_at:
        return "Bessrochno"
    try:
        exp = datetime.fromisoformat(expires_at)
        now = datetime.now()
        if exp <= now:
            return "Istek"
        diff = (exp - now).days
        if diff == 0:
            hours = (exp - now).seconds // 3600
            return str(hours) + "h"
        return str(diff) + "d"
    except:
        return "?"


async def safe_edit(message, text, reply_markup=None):
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except TelegramBadRequest:
        await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


async def safe_send(message, text, reply_markup=None):
    await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


@dp.message(CommandStart())
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    name = msg.from_user.first_name
    text = "<b>Nefrit VPN</b>\n\n"
    text = text + "Dobro pozhalovat, " + name + "!\n\n"
    text = text + "Bystry i nadezhny VPN servis."
    await msg.answer(text, reply_markup=main_kb(is_admin(msg.from_user)), parse_mode="HTML")


@dp.callback_query(F.data == "back")
async def go_back(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(cb.message, "<b>Nefrit VPN</b> - Menu", main_kb(is_admin(cb.from_user)))
    await cb.answer()


@dp.callback_query(F.data == "activate")
async def activate(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(States.waiting_key)
    text = "<b>Vvedite kluch aktivatsii:</b>\n\n"
    text = text + "Primer: NEFRIT-A1B2C3D4E5F6G7H8"
    await safe_edit(cb.message, text, cancel_kb())
    await cb.answer()


@dp.message(States.waiting_key)
async def process_key(msg: types.Message, state: FSMContext):
    key = msg.text.strip().upper()
    username = msg.from_user.username
    if not username:
        username = msg.from_user.first_name

    path, error = await activate_key(key, msg.from_user.id, username)
    await state.clear()

    if error:
        await safe_send(msg, "Oshibka: " + error, back_kb())
        return

    info = await get_user_info(msg.from_user.id)
    if not info:
        await safe_send(msg, "Oshibka polucheniya dannyh", back_kb())
        return

    user_path = info[0]
    user_uuid = info[1]
    expires_at = info[3]

    link = generate_vless_link(user_uuid, user_path)
    sub_url = BASE_URL + "/sub/" + user_path

    if expires_at:
        exp = datetime.fromisoformat(expires_at)
        exp_str = "Deystvuet do: " + exp.strftime("%d.%m.%Y %H:%M")
    else:
        exp_str = "Srok: Bessrochno"

    text = "<b>Podpiska aktivirovana!</b>\n\n"
    text = text + exp_str + "\n\n"
    text = text + "<b>Ssylka podpiski:</b>\n"
    text = text + "<code>" + sub_url + "</code>\n\n"
    text = text + "<b>Pryamoy config:</b>\n"
    text = text + "<code>" + link + "</code>\n\n"
    text = text + "<b>Prilozheniya:</b>\n"
    text = text + "Android: V2rayNG\n"
    text = text + "iOS: Streisand / V2Box\n"
    text = text + "Windows: V2rayN\n"
    text = text + "macOS: V2rayU"

    await safe_send(msg, text, back_kb())


@dp.callback_query(F.data == "mysub")
async def my_sub(cb: types.CallbackQuery):
    info = await get_user_info(cb.from_user.id)

    if not info:
        text = "<b>U vas net aktivnoy podpiski</b>\n\n"
        text = text + "Nazhmite Aktivirovat dlya aktivatsii."
        await safe_edit(cb.message, text, back_kb())
        await cb.answer()
        return

    user_path = info[0]
    user_uuid = info[1]
    is_active = info[2]
    expires_at = info[3]

    link = generate_vless_link(user_uuid, user_path)
    sub_url = BASE_URL + "/sub/" + user_path

    if is_active:
        status = "Aktivna"
    else:
        status = "Neaktivna"

    if expires_at:
        exp = datetime.fromisoformat(expires_at)
        now = datetime.now()
        if exp > now:
            diff = (exp - now).days
            exp_str = exp.strftime("%d.%m.%Y") + " (" + str(diff) + " dney)"
        else:
            exp_str = "Istek"
    else:
        exp_str = "Bessrochno"

    text = "<b>Vasha podpiska</b>\n\n"
    text = text + "Status: " + status + "\n"
    text = text + "Srok: " + exp_str + "\n"
    text = text + "ID: " + user_path + "\n\n"
    text = text + "<b>Ssylka:</b>\n<code>" + sub_url + "</code>\n\n"
    text = text + "<b>Config:</b>\n<code>" + link + "</code>"

    await safe_edit(cb.message, text, back_kb())
    await cb.answer()


@dp.callback_query(F.data == "admin")
async def admin_panel(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user):
        await cb.answer("Dostup zapreschen", show_alert=True)
        return

    await state.clear()
    active, total, free_keys, total_keys = await get_stats()

    xray_ok = xray_process is not None and xray_process.poll() is None
    xray_status = "Rabotaet" if xray_ok else "Ostanovlen"

    text = "<b>Admin panel</b>\n\n"
    text = text + "Polzovateley: " + str(active) + " / " + str(total) + "\n"
    text = text + "Kluchey: " + str(free_keys) + " / " + str(total_keys) + "\n"
    text = text + "Xray: " + xray_status

    await safe_edit(cb.message, text, admin_kb())
    await cb.answer()


@dp.callback_query(F.data == "newkey")
async def new_key_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user):
        await cb.answer("Dostup zapreschen", show_alert=True)
        return

    await state.set_state(States.waiting_days)
    text = "<b>Sozdanie klucha</b>\n\n"
    text = text + "Vyberite srok deystviya ili vvedite chislo dney:"
    await safe_edit(cb.message, text, days_kb())
    await cb.answer()


@dp.callback_query(F.data.startswith("days_"))
async def process_days_button(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user):
        await cb.answer("Dostup zapreschen", show_alert=True)
        return

    val = cb.data.replace("days_", "")

    if val == "0":
        days = None
        days_str = "Bessrochno"
    else:
        days = int(val)
        days_str = str(days) + " dney"

    await state.clear()
    key, key_id = await create_key(days)

    text = "<b>Kluch sozdan!</b>\n\n"
    text = text + "ID: #" + str(key_id) + "\n"
    text = text + "Kluch: <code>" + key + "</code>\n"
    text = text + "Srok: " + days_str + "\n\n"
    text = text + "<i>Nazhmite na kluch chtoby skopirovat</i>"

    await safe_edit(cb.message, text, back_admin_kb())
    await cb.answer()


@dp.message(States.waiting_days)
async def process_days_manual(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user):
        return

    try:
        days = int(msg.text.strip())
        if days <= 0:
            await safe_send(msg, "Vvedite polozhitelnoe chislo", back_admin_kb())
            return
    except:
        await safe_send(msg, "Vvedite chislo dney", back_admin_kb())
        return

    await state.clear()
    key, key_id = await create_key(days)

    text = "<b>Kluch sozdan!</b>\n\n"
    text = text + "ID: #" + str(key_id) + "\n"
    text = text + "Kluch: <code>" + key + "</code>\n"
    text = text + "Srok: " + str(days) + " dney\n\n"
    text = text + "<i>Nazhmite na kluch chtoby skopirovat</i>"

    await safe_send(msg, text, back_admin_kb())


@dp.callback_query(F.data == "keys")
async def list_keys(cb: types.CallbackQuery):
    if not is_admin(cb.from_user):
        await cb.answer("Dostup zapreschen", show_alert=True)
        return

    keys = await get_keys_list()

    if not keys:
        text = "<b>Kluchey poka net</b>"
    else:
        lines = ["<b>Spisok kluchey:</b>\n"]

        for row in keys:
            key_id = row[0]
            key = row[1]
            days = row[2]
            is_used = row[3]
            username = row[4]
            expires_at = row[5]
            is_revoked = row[6]

            if is_revoked:
                status = "[X]"
            elif is_used:
                status = "[V]"
            else:
                status = "[O]"

            if days is None:
                days_str = "inf"
            else:
                days_str = str(days) + "d"

            if username:
                user_str = "@" + username
            elif is_used:
                user_str = "no @"
            else:
                user_str = "-"

            exp_str = format_expiry(expires_at, is_revoked)

            line = status + " #" + str(key_id) + " | " + days_str + " | " + user_str + " | " + exp_str
            lines.append(line)

        text = "\n".join(lines)

    if len(text) > 4000:
        text = text[:4000] + "\n..."

    await safe_edit(cb.message, text, back_admin_kb())
    await cb.answer()


@dp.callback_query(F.data == "revoke")
async def revoke_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user):
        await cb.answer("Dostup zapreschen", show_alert=True)
        return

    await state.set_state(States.waiting_revoke_id)
    text = "<b>Annulirovanie klucha</b>\n\n"
    text = text + "Vvedite ID klucha (chislo posle #):\n\n"
    text = text + "Primer: 5\n\n"
    text = text + "Polzovatel poteryaet dostup!"
    await safe_edit(cb.message, text, back_admin_kb())
    await cb.answer()


@dp.message(States.waiting_revoke_id)
async def process_revoke(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user):
        return

    try:
        key_id = int(msg.text.strip().replace("#", ""))
    except:
        await safe_send(msg, "Vvedite korrektny ID", back_admin_kb())
        return

    info = await get_key_info(key_id)

    if not info:
        await state.clear()
        await safe_send(msg, "Kluch ne nayden", back_admin_kb())
        return

    key = info[1]
    username = info[4]
    is_revoked = info[6]

    if is_revoked:
        await state.clear()
        await safe_send(msg, "Kluch uzhe annulirovan", back_admin_kb())
        return

    await revoke_key(key_id)
    await state.clear()

    if username:
        user_str = "@" + username
    else:
        user_str = "-"

    text = "<b>Kluch annulirovan!</b>\n\n"
    text = text + "ID: #" + str(key_id) + "\n"
    text = text + "Kluch: <code>" + key + "</code>\n"
    text = text + "Polzovatel: " + user_str + "\n\n"
    text = text + "Dostup k VPN otozvan."

    await safe_send(msg, text, back_admin_kb())


@dp.callback_query(F.data == "stats")
async def stats_handler(cb: types.CallbackQuery):
    if not is_admin(cb.from_user):
        await cb.answer("Dostup zapreschen", show_alert=True)
        return

    active, total, free_keys, total_keys = await get_stats()

    text = "<b>Statistika Nefrit VPN</b>\n\n"
    text = text + "<b>Polzovateli:</b>\n"
    text = text + "Aktivnyh: " + str(active) + "\n"
    text = text + "Vsego: " + str(total) + "\n\n"
    text = text + "<b>Kluchi:</b>\n"
    text = text + "Svobodnyh: " + str(free_keys) + "\n"
    text = text + "Vsego: " + str(total_keys)

    await safe_edit(cb.message, text, back_admin_kb())
    await cb.answer()


@dp.callback_query(F.data == "restart_xray")
async def restart_xray_handler(cb: types.CallbackQuery):
    if not is_admin(cb.from_user):
        await cb.answer("Dostup zapreschen", show_alert=True)
        return

    await cb.answer("Perezapusk Xray...")
    await restart_xray()

    await safe_edit(cb.message, "<b>Xray perezapuschen!</b>", back_admin_kb())


async def run_bot():
    print("Starting Telegram bot...")
    await dp.start_polling(bot)


async def run_web():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/sub/{path}", handle_subscription)
    app.router.add_get("/tunnel", handle_tunnel)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print("Web server started on port " + str(PORT))

    while True:
        await asyncio.sleep(3600)


async def expiry_checker():
    while True:
        await asyncio.sleep(3600)
        await check_expired_users()
        await restart_xray()
        print("Expiry check completed")


async def main():
    print("=" * 50)
    print("NEFRIT VPN SERVER")
    print("=" * 50)

    await init_db()
    print("Database initialized")

    await generate_xray_config()
    start_xray()
    await asyncio.sleep(3)

    if xray_process and xray_process.poll() is None:
        print("Xray is running")
    else:
        print("Xray may not be running, check logs")

    try:
        await asyncio.gather(
            run_web(),
            run_bot(),
            expiry_checker()
        )
    except KeyboardInterrupt:
        print("Shutting down...")
        stop_xray()


if __name__ == "__main__":
    asyncio.run(main())
