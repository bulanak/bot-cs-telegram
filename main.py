import sqlite3
import time
import os
import html
from datetime import datetime
from telethon import TelegramClient, events, Button

# =========================================================
# KONFIGURASI
# =========================================================
API_ID   = int(os.environ.get("API_ID", 35443397))
API_HASH = os.environ.get("API_HASH", "4888086e2b51b7f0fb98de5eb419e468")

GROUP_ADMIN_ID = int(os.environ.get("GROUP_ADMIN_ID", -1004488215589))
SPAM_COOLDOWN  = 30
DB_NAME        = "bot_cs_data.db"

client = TelegramClient('sesi_cs_pribadi', API_ID, API_HASH)


# =========================================================
# DATABASE
# =========================================================
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS responded_users (user_id INTEGER PRIMARY KEY)")
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('nama_admin', 'Siti')")
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_store_open', 'True')")
        conn.commit()


def get_setting(key, default=None):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default


def update_setting(key, value):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
        conn.commit()


# =========================================================
# HELPER
# =========================================================
_memory_users: set[int] = set()
_last_message_time: dict[int, float] = {}


def is_user_responded(user_id: int) -> bool:
    if user_id in _memory_users:
        return True
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM responded_users WHERE user_id = ?", (user_id,))
        found = cur.fetchone() is not None
    if found:
        _memory_users.add(user_id)
    return found


def add_responded_user(user_id: int):
    _memory_users.add(user_id)
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO responded_users (user_id) VALUES (?)", (user_id,))
        conn.commit()


def is_spamming(user_id: int) -> bool:
    now = time.time()
    last = _last_message_time.get(user_id, 0)
    if now - last < SPAM_COOLDOWN:
        return True
    _last_message_time[user_id] = now
    return False


def _count_users() -> int:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM responded_users")
        return cur.fetchone()[0]


# =========================================================
# TEMPLATE PESAN
# =========================================================
def msg_welcome() -> str:
    return (
        "Halo, Kak. 👋\n\n"
        "Terima kasih telah menghubungi layanan Customer Service kami.\n"
        "Pesan Kakak telah kami terima dengan baik.\n\n"
        "Mohon menunggu sebentar, admin kami akan segera menghubungkan "
        "Kakak dengan CS yang bertugas. 🙏\n\n"
        "Salam,\n"
        "Tim Customer Service"
    )


def msg_closed() -> str:
    return (
        "Halo, Kak. 👋\n\n"
        "Mohon maaf, saat ini layanan Customer Service kami sedang TUTUP "
        "atau di luar jam operasional. 🕐\n\n"
        "Pesan Kakak telah kami simpan dan akan segera dibalas begitu "
        "jam operasional kami buka kembali.\n\n"
        "Terima kasih atas pengertiannya. 🙏\n\n"
        "Salam,\n"
        "Tim Customer Service"
    )


def msg_connected(nama_admin: str) -> str:
    return (
        "Halo, Kak. 😊\n\n"
        f"Saat ini Kakak telah terhubung dengan CS kami, {nama_admin}.\n\n"
        "Silakan sampaikan pertanyaan atau keluhan Kakak. "
        "Kami siap membantu.\n\n"
        "Terima kasih.\n"
        "Tim Customer Service"
    )


def msg_report(sender, text: str) -> str:
    uname = f"@{sender.username}" if sender.username else "Tidak tersedia"
    waktu = datetime.now().strftime("%d %b %Y • %H:%M")
    safe_text = html.escape(text)
    safe_name = html.escape(sender.first_name or "-")

    return (
        "📩 <b>PELANGGAN BARU MASUK</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Nama</b>     : {safe_name}\n"
        f"🔗 <b>Username</b> : {uname}\n"
        f"🆔 <b>User ID</b>  : <code>{sender.id}</code>\n"
        f"🕐 <b>Waktu</b>    : {waktu}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>Pesan:</b>\n<blockquote>{safe_text}</blockquote>\n\n"
        "Silakan pilih aksi di bawah ini, Kak:"
    )


# =========================================================
# 1. COMMAND ADMIN
# =========================================================
@client.on(events.NewMessage(outgoing=True))
async def owner_commands(event):
    text = event.raw_text.strip()

    # Ganti nama admin
    if text.startswith('.admin '):
        nama_baru = text.split('.admin ', 1)[1].strip()
        if nama_baru:
            update_setting('nama_admin', nama_baru)
            await event.edit(
                f"✅ <b>BERHASIL</b>\n\n"
                f"Nama admin CS telah diubah menjadi: <b>{nama_baru}</b>",
                parse_mode='html'
            )
        else:
            await event.edit("⚠️ Format: <code>.admin NamaAdmin</code>", parse_mode='html')

    # Buka toko
    elif text == '.open':
        update_setting('is_store_open', 'True')
        await event.edit("🟢 <b>STATUS CS: BUKA</b>\n\nLayanan CS telah diaktifkan kembali.", parse_mode='html')

    # Tutup toko
    elif text == '.close':
        update_setting('is_store_open', 'False')
        await event.edit("🔴 <b>STATUS CS: TUTUP</b>\n\nLayanan CS telah dinonaktifkan.", parse_mode='html')

    # Cek status
    elif text == '.status':
        nama_aktif = get_setting('nama_admin')
        is_open    = get_setting('is_store_open') == 'True'
        status     = "🟢 BUKA" if is_open else "🔴 TUTUP"
        total_user = len(_memory_users) or _count_users()

        await event.edit(
            "📊 <b>STATUS CS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👩‍💼 <b>Admin Aktif</b>     : {nama_aktif}\n"
            f"🏪 <b>Status Toko</b>     : {status}\n"
            f"👥 <b>Total Pelanggan</b> : {total_user}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 Perintah:\n"
            "<code>.admin Nama</code>\n"
            "<code>.open</code> | <code>.close</code> | <code>.status</code>\n"
            "<code>.terhubung USER_ID</code>",
            parse_mode='html'
        )

    # ── HUBUNGKAN PELANGGAN MANUAL ─────────────────────
    elif text.startswith('.terhubung '):
        arg = text.split('.terhubung ', 1)[1].strip()

        if not arg.isdigit():
            await event.edit(
                "⚠️ <b>Format salah, Kak.</b>\n\n"
                "Gunakan: <code>.terhubung 123456789</code>",
                parse_mode='html'
            )
            return

        target_user_id = int(arg)
        nama_aktif = get_setting('nama_admin')

        try:
            await client.send_message(target_user_id, msg_connected(nama_aktif))
            await event.edit(
                f"✅ <b>BERHASIL TERHUBUNG</b>\n\n"
                f"Pesan terhubung sudah dikirim ke pelanggan:\n"
                f"🆔 User ID : <code>{target_user_id}</code>\n"
                f"👩‍💼 Admin  : <b>{nama_aktif}</b>",
                parse_mode='html'
            )
            print(f"[CONNECT] Terhubung dengan user {target_user_id} via {nama_aktif}")
        except Exception as e:
            print(f"[ERROR CONNECT] {type(e).__name__}: {e}")
            await event.edit(
                "❌ <b>GAGAL</b>\n\n"
                f"Tidak bisa mengirim pesan ke user ID <code>{target_user_id}</code>.\n"
                "Kemungkinan: user ID salah, bot belum pernah di-chat, "
                "atau user memblokir bot.",
                parse_mode='html'
            )


# =========================================================
# 2. AUTO WELCOME + LAPORAN
# =========================================================
@client.on(events.NewMessage(incoming=True))
async def auto_reply(event):
    if not (event.is_private and not event.out):
        return

    sender_id = event.sender_id
    is_open   = get_setting('is_store_open') == 'True'

    if not is_open:
        if not is_user_responded(sender_id):
            await event.reply(msg_closed())
            add_responded_user(sender_id)
        return

    if is_spamming(sender_id):
        return

    if not is_user_responded(sender_id):
        sender = await event.get_sender()
        await event.reply(msg_welcome())
        add_responded_user(sender_id)

        keyboard = [
            [Button.inline("🔗 Hubungkan Pelanggan", data=f"connect_{sender_id}")],
            [
                Button.inline("👤 Lihat Profil", data=f"profile_{sender_id}"),
                Button.inline("✅ Tandai Selesai", data=f"done_{sender_id}"),
            ],
        ]

        try:
            await client.send_message(
                GROUP_ADMIN_ID,
                msg_report(sender, event.raw_text),
                parse_mode='html',
                buttons=keyboard,
            )
            print(f"[REPORT] Laporan dikirim untuk user {sender_id}")
        except Exception as e:
            print(f"[ERROR GRUP] {type(e).__name__}: {e}")


# =========================================================
# 3. HANDLE TOMBOL (Kalau muncul)
# =========================================================
@client.on(events.CallbackQuery(pattern=b"connect_"))
async def handle_connect(event):
    try:
        target_user_id = int(event.data.decode().split("_")[1])
    except (IndexError, ValueError):
        return await event.answer("⚠️ Data tidak valid.", alert=True)

    nama_aktif = get_setting('nama_admin')
    try:
        await client.send_message(target_user_id, msg_connected(nama_aktif))
    except Exception as e:
        print(f"[ERROR SEND] {e}")
        return await event.answer("❌ Gagal menghubungi pelanggan.", alert=True)

    new_buttons = [
        [
            Button.inline("👤 Lihat Profil", data=f"profile_{target_user_id}"),
            Button.inline("✅ Tandai Selesai", data=f"done_{target_user_id}"),
        ]
    ]
    await event.edit(
        text=event.message.text + f"\n\n✅ <b>STATUS:</b> Terhubung dengan <b>{nama_aktif}</b>.",
        buttons=new_buttons,
        parse_mode='html'
    )
    await event.answer(f"✅ Terhubung dengan {nama_aktif}.")


@client.on(events.CallbackQuery(pattern=b"profile_"))
async def handle_profile(event):
    try:
        target_user_id = int(event.data.decode().split("_")[1])
    except (IndexError, ValueError):
        return await event.answer("⚠️ Data tidak valid.", alert=True)
    try:
        user = await client.get_entity(target_user_id)
        uname = f"@{user.username}" if user.username else "Tidak tersedia"
        info = (
            f"👤 Profil Pelanggan\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"Nama     : {user.first_name or '-'}\n"
            f"Username : {uname}\n"
            f"User ID  : {user.id}"
        )
        await event.answer(info, alert=True)
    except Exception as e:
        print(f"[ERROR PROFILE] {e}")
        await event.answer("❌ Tidak bisa memuat profil.", alert=True)


@client.on(events.CallbackQuery(pattern=b"done_"))
async def handle_done(event):
    await event.edit(
        text=event.message.text + "\n\n✅ <b>STATUS:</b> Percakapan ditandai selesai.",
        buttons=None,
        parse_mode='html'
    )
    await event.answer("✅ Percakapan ditandai selesai.")


# =========================================================
# MAIN
# =========================================================
def main():
    init_db()
    print("=" * 50)
    print("   USERBOT CS - PROFESSIONAL EDITION")
    print("=" * 50)
    print(f"Admin Aktif : {get_setting('nama_admin')}")
    print(f"Status Toko : {'BUKA' if get_setting('is_store_open') == 'True' else 'TUTUP'}")
    print("-" * 50)
    client.start()
    client.run_until_disconnected()


if __name__ == '__main__':
    main()
