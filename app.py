from datetime import datetime, timedelta
import base64
import json
import os
import sqlite3
import uuid

from flask import Flask, redirect, render_template, request, session
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")
app.permanent_session_lifetime = timedelta(days=30)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "148corleone")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
AVATAR_FOLDER = os.path.join(BASE_DIR, "static", "img")
IMG_FOLDER = os.path.join(BASE_DIR, "static", "img")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".gif", ".bmp"}


def now_time():
    return datetime.now().strftime("%H:%M")


def now_full():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def now_display():
    return datetime.now().strftime("%d-%m-%Y %H:%M")


def encode_image(file):
    if not file or not file.filename:
        return None

    data = file.read()
    if not data:
        return None

    mime = file.mimetype or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def save_admin_image(file, prefix):
    filename, _ = save_uploaded_file(file, IMG_FOLDER, prefix)
    return filename


def save_uploaded_file(file, folder, prefix):
    if not file or not file.filename:
        return None, None

    original_name = secure_filename(file.filename)
    raw_name = file.filename or ""
    ext = os.path.splitext(original_name or raw_name)[1].lower()
    data = file.read()
    if len(data) < 128:
        return None, None

    mime_ext = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
    }.get((file.mimetype or "").lower(), "")

    if data.startswith(b"\xff\xd8\xff"):
        ext = ".jpg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        ext = ".png"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        ext = ".webp"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        ext = ".gif"
    elif data.startswith(b"BM"):
        ext = ".bmp"
    elif mime_ext:
        ext = mime_ext

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None, None

    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}{ext}"
    with open(os.path.join(folder, filename), "wb") as saved_file:
        saved_file.write(data)

    return filename, original_name or raw_name


def clean_external_link(value):
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("@"):
        return f"https://t.me/{value[1:]}"
    if value.startswith("t.me/"):
        return f"https://{value}"
    if value.startswith(("http://", "https://")):
        return value
    return f"https://{value}"


def firebase_client():
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError:
        return None, None

    credentials_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    candidates = [
        os.environ.get("FIREBASE_CREDENTIALS_PATH"),
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        os.path.join(BASE_DIR, "firebase_key.json"),
    ]
    key_path = next((path for path in candidates if path and os.path.exists(path)), None)
    if not key_path and not credentials_json:
        return None, None

    if not firebase_admin._apps:
        if credentials_json:
            cred = credentials.Certificate(json.loads(credentials_json))
        else:
            cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)

    return firestore.client(), firestore


FIREBASE_DB, FIRESTORE = firebase_client()

DEFAULT_CARDS = [
    {
        "id": "default:cryptonyx",
        "default_slug": "cryptonyx",
        "section": "pmr_exchange",
        "title": "CryptonyX",
        "description": "USDT / LTC",
        "image_src": "cryptonyx.jpg",
        "link": "https://t.me/cryptonyxor",
        "is_default": True,
    },
    {
        "id": "default:sinaloa_pmr",
        "default_slug": "sinaloa_pmr",
        "section": "pmr_shop",
        "title": "SINALOA",
        "description": "MD / PMR",
        "image_src": "sinaloa.jpg",
        "link": "https://t.me/SINALOAPMR",
        "is_default": True,
    },
    {
        "id": "default:kryptomah",
        "default_slug": "kryptomah",
        "section": "md_exchange",
        "title": "KryptoMah",
        "description": "MD CASH",
        "image_src": "kryptomah.jpg",
        "link": "#",
        "is_default": True,
    },
    {
        "id": "default:ghostcrypto",
        "default_slug": "ghostcrypto",
        "section": "md_exchange",
        "title": "GhostCrypto",
        "description": "Обменник",
        "image_src": "ghost.jpg",
        "link": "#",
        "is_default": True,
    },
    {
        "id": "default:sinaloa_md",
        "default_slug": "sinaloa_md",
        "section": "md_shop",
        "title": "SINALOA",
        "description": "Молдова",
        "image_src": "sinaloa.jpg",
        "link": "https://t.me/SINALOAPMR",
        "is_default": True,
    },
    {
        "id": "default:red_queen",
        "default_slug": "red_queen",
        "section": "services",
        "title": "Red Queen",
        "description": "Продажа/Покупка банковских карт и кошельков (ПМР/МД)",
        "image_src": "redq.png",
        "link": "https://t.me/umbrella01",
        "is_default": True,
    },
]



def db():
    return sqlite3.connect(DB_PATH)


def ensure_column(cursor, table, column, definition):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]

    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_storage():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(AVATAR_FOLDER, exist_ok=True)

    if FIREBASE_DB:
        return

    conn = db()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            avatar TEXT DEFAULT 'default.jpg',
            role TEXT DEFAULT 'Пользователь',
            created_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            message TEXT,
            time TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            image TEXT NOT NULL,
            link TEXT NOT NULL,
            created_at TEXT
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS hidden_default_cards (
            slug TEXT PRIMARY KEY,
            hidden_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS default_card_overrides (
            slug TEXT PRIMARY KEY,
            section TEXT,
            title TEXT,
            description TEXT,
            image_src TEXT,
            link TEXT,
            updated_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
        """
    )
    ensure_column(c, "chat", "file", "TEXT")
    ensure_column(c, "chat", "file_name", "TEXT")
    ensure_column(c, "chat", "message_type", "TEXT DEFAULT 'text'")
    ensure_column(c, "chat", "pinned", "INTEGER DEFAULT 0")
    ensure_column(c, "chat", "edited_at", "TEXT")
    ensure_column(c, "chat", "created_at", "TEXT")
    ensure_column(c, "chat", "reply_to", "TEXT")
    ensure_column(c, "chat", "likes", "INTEGER DEFAULT 0")
    ensure_column(c, "chat", "fires", "INTEGER DEFAULT 0")
    ensure_column(c, "chat", "hearts", "INTEGER DEFAULT 0")
    ensure_column(c, "cards", "image_src", "TEXT")
    c.execute("UPDATE users SET avatar='default.jpg' WHERE avatar IS NULL OR avatar='default.png'")
    conn.commit()
    conn.close()


init_storage()


class Store:
    @staticmethod
    def using_firebase():
        return FIREBASE_DB is not None

    @staticmethod
    def get_setting(key, default=None):
        if FIREBASE_DB:
            doc = FIREBASE_DB.collection("settings").document(key).get()
            if not doc.exists:
                return default
            return doc.to_dict().get("value", default)

        conn = db()
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else default

    @staticmethod
    def set_setting(key, value):
        if FIREBASE_DB:
            FIREBASE_DB.collection("settings").document(key).set(
                {"value": value, "updated_at": now_display()},
                merge=True,
            )
            return

        conn = db()
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now_display()),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def users_count():
        if FIREBASE_DB:
            return sum(1 for _ in FIREBASE_DB.collection("users").stream())

        conn = db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        count = c.fetchone()[0]
        conn.close()
        return count

    @staticmethod
    def create_user(username, password):
        if FIREBASE_DB:
            doc = FIREBASE_DB.collection("users").document(username)
            if doc.get().exists:
                return False
            doc.set(
                {
                    "username": username,
                    "password": password,
                    "avatar": "default.jpg",
                    "role": "Пользователь",
                    "created_at": now_display(),
                }
            )
            return True

        conn = db()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (username, password, avatar, created_at) VALUES (?, ?, ?, ?)",
                (username, password, "default.jpg", now_display()),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    @staticmethod
    def check_user(username, password):
        if FIREBASE_DB:
            doc = FIREBASE_DB.collection("users").document(username).get()
            return doc.exists and doc.to_dict().get("password") == password

        conn = db()
        c = conn.cursor()
        c.execute("SELECT 1 FROM users WHERE username=? AND password=?", (username, password))
        result = c.fetchone()
        conn.close()
        return bool(result)

    @staticmethod
    def user_avatar(username):
        if FIREBASE_DB:
            doc = FIREBASE_DB.collection("users").document(username).get()
            if doc.exists:
                return doc.to_dict().get("avatar") or "default.jpg"
            return "default.jpg"

        conn = db()
        c = conn.cursor()
        c.execute("SELECT avatar FROM users WHERE username=?", (username,))
        result = c.fetchone()
        conn.close()
        return result[0] if result and result[0] else "default.jpg"

    @staticmethod
    def update_avatar(username, filename):
        if FIREBASE_DB:
            FIREBASE_DB.collection("users").document(username).set({"avatar": filename}, merge=True)
            return

        conn = db()
        c = conn.cursor()
        c.execute("UPDATE users SET avatar=? WHERE username=?", (filename, username))
        conn.commit()
        conn.close()

    @staticmethod
    def hidden_default_card_slugs():
        if FIREBASE_DB:
            return {doc.id for doc in FIREBASE_DB.collection("hidden_default_cards").stream()}

        conn = db()
        c = conn.cursor()
        c.execute("SELECT slug FROM hidden_default_cards")
        hidden = {row[0] for row in c.fetchall()}
        conn.close()
        return hidden

    @staticmethod
    def default_card_overrides():
        if FIREBASE_DB:
            overrides = {}
            for doc in FIREBASE_DB.collection("default_card_overrides").stream():
                overrides[doc.id] = doc.to_dict()
            return overrides

        conn = db()
        c = conn.cursor()
        c.execute("SELECT slug, section, title, description, image_src, link FROM default_card_overrides")
        overrides = {
            row[0]: {
                "section": row[1],
                "title": row[2],
                "description": row[3],
                "image_src": row[4],
                "link": row[5],
            }
            for row in c.fetchall()
        }
        conn.close()
        return overrides

    @staticmethod
    def default_cards(include_hidden=False):
        hidden = set() if include_hidden else Store.hidden_default_card_slugs()
        overrides = Store.default_card_overrides()
        cards = []
        for card in DEFAULT_CARDS:
            if card["default_slug"] in hidden:
                continue
            item = dict(card)
            override = overrides.get(card["default_slug"]) or {}
            for key in ("section", "title", "description", "image_src", "link"):
                if override.get(key):
                    item[key] = override[key]
            cards.append(item)
        return cards

    @staticmethod
    def all_admin_cards():
        defaults = Store.default_cards()
        dynamic = Store.cards()
        return defaults + dynamic

    @staticmethod
    def hide_default_card(slug):
        if FIREBASE_DB:
            FIREBASE_DB.collection("hidden_default_cards").document(slug).set({"hidden_at": now_display()})
            return

        conn = db()
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO hidden_default_cards (slug, hidden_at) VALUES (?, ?)",
            (slug, now_display()),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def cards():
        if FIREBASE_DB:
            cards = []
            for doc in FIREBASE_DB.collection("cards").stream():
                item = doc.to_dict()
                item["id"] = doc.id
                item["image_src"] = item.get("image_src") or item.get("image") or ""
                cards.append(item)
            return sorted(cards, key=lambda item: item.get("created_at", ""), reverse=True)

        conn = db()
        c = conn.cursor()
        c.execute("SELECT id, section, title, description, image, link, COALESCE(image_src, '') FROM cards ORDER BY id DESC")
        rows = c.fetchall()
        conn.close()
        return [
            {
                "id": str(row[0]),
                "section": row[1],
                "title": row[2],
                "description": row[3],
                "image": row[4],
                "link": row[5],
                "image_src": row[6] or row[4],
            }
            for row in rows
        ]

    @staticmethod
    def add_card(section, title, description, link, image_src):
        if FIREBASE_DB:
            FIREBASE_DB.collection("cards").document(str(uuid.uuid4())).set(
                {
                    "section": section,
                    "title": title,
                    "description": description,
                    "image": image_src,
                    "image_src": image_src,
                    "link": link,
                    "created_at": now_full(),
                }
            )
            return

        conn = db()
        c = conn.cursor()
        image_name = image_src if not image_src.startswith("data:") else "uploaded"
        c.execute(
            """
            INSERT INTO cards (section, title, description, image, image_src, link, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (section, title, description, image_name, image_src, link, now_display()),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_card(card_id):
        if str(card_id).startswith("default:"):
            slug = str(card_id).split(":", 1)[1]
            for card in Store.default_cards(include_hidden=True):
                if card["default_slug"] == slug:
                    return dict(card)
            return None

        if FIREBASE_DB:
            doc = FIREBASE_DB.collection("cards").document(card_id).get()
            if not doc.exists:
                return None
            item = doc.to_dict()
            item["id"] = doc.id
            item["image_src"] = item.get("image_src") or item.get("image") or ""
            return item

        conn = db()
        c = conn.cursor()
        c.execute("SELECT id, section, title, description, image, link, COALESCE(image_src, '') FROM cards WHERE id=?", (card_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "section": row[1],
            "title": row[2],
            "description": row[3],
            "image": row[4],
            "link": row[5],
            "image_src": row[6] or row[4],
        }

    @staticmethod
    def update_card(card_id, section, title, description, link, image_src=None):
        if str(card_id).startswith("default:"):
            slug = str(card_id).split(":", 1)[1]
            current = Store.get_card(card_id)
            if not current:
                return
            image_value = image_src or current.get("image_src") or current.get("image") or ""
            payload = {
                "section": section,
                "title": title,
                "description": description,
                "link": link,
                "image_src": image_value,
                "updated_at": now_display(),
            }
            if FIREBASE_DB:
                FIREBASE_DB.collection("default_card_overrides").document(slug).set(payload, merge=True)
                return

            conn = db()
            c = conn.cursor()
            c.execute(
                """
                INSERT OR REPLACE INTO default_card_overrides
                    (slug, section, title, description, image_src, link, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (slug, section, title, description, image_value, link, now_display()),
            )
            conn.commit()
            conn.close()
            return

        payload = {
            "section": section,
            "title": title,
            "description": description,
            "link": link,
        }
        if image_src:
            payload["image"] = image_src
            payload["image_src"] = image_src

        if FIREBASE_DB:
            FIREBASE_DB.collection("cards").document(card_id).set(payload, merge=True)
            return

        conn = db()
        c = conn.cursor()
        if image_src:
            image_name = image_src if not image_src.startswith("data:") else "uploaded"
            c.execute(
                """
                UPDATE cards
                SET section=?, title=?, description=?, link=?, image=?, image_src=?
                WHERE id=?
                """,
                (section, title, description, link, image_name, image_src, card_id),
            )
        else:
            c.execute(
                """
                UPDATE cards
                SET section=?, title=?, description=?, link=?
                WHERE id=?
                """,
                (section, title, description, link, card_id),
            )
        conn.commit()
        conn.close()

    @staticmethod
    def delete_card(card_id):
        if str(card_id).startswith("default:"):
            Store.hide_default_card(str(card_id).split(":", 1)[1])
            return

        if FIREBASE_DB:
            FIREBASE_DB.collection("cards").document(card_id).delete()
            return

        conn = db()
        c = conn.cursor()
        c.execute("DELETE FROM cards WHERE id=?", (card_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def add_message(user, message, file_name, original_name, message_type, reply_to):
        payload = {
            "user": user,
            "message": message,
            "time": now_time(),
            "file": file_name,
            "file_name": original_name,
            "message_type": message_type,
            "pinned": 0,
            "edited_at": None,
            "created_at": now_full(),
            "reply_to": reply_to,
            "likes": 0,
            "fires": 0,
            "hearts": 0,
        }

        if FIREBASE_DB:
            FIREBASE_DB.collection("chat").document(str(uuid.uuid4())).set(payload)
            return

        conn = db()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO chat (user, message, time, file, file_name, message_type, created_at, reply_to, likes, fires, hearts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
            """,
            (user, message, payload["time"], file_name, original_name, message_type, payload["created_at"], reply_to),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def messages():
        users = {}
        if FIREBASE_DB:
            for doc in FIREBASE_DB.collection("users").stream():
                users[doc.id] = doc.to_dict()

            rows = []
            for doc in FIREBASE_DB.collection("chat").stream():
                item = doc.to_dict()
                item["id"] = doc.id
                rows.append(item)
        else:
            conn = db()
            c = conn.cursor()
            c.execute(
                """
                SELECT id, user, message, time, file, file_name, message_type, pinned,
                       edited_at, created_at, reply_to, likes, fires, hearts
                FROM chat
                """
            )
            rows = [
                {
                    "id": str(row[0]),
                    "user": row[1],
                    "message": row[2],
                    "time": row[3],
                    "file": row[4],
                    "file_name": row[5],
                    "message_type": row[6],
                    "pinned": row[7] or 0,
                    "edited_at": row[8],
                    "created_at": row[9],
                    "reply_to": str(row[10]) if row[10] else None,
                    "likes": row[11] or 0,
                    "fires": row[12] or 0,
                    "hearts": row[13] or 0,
                }
                for row in c.fetchall()
            ]
            c.execute("SELECT username, avatar, role FROM users")
            users = {row[0]: {"avatar": row[1], "role": row[2]} for row in c.fetchall()}
            conn.close()

        by_id = {str(item["id"]): item for item in rows}
        rows = sorted(rows, key=lambda item: (-(item.get("pinned") or 0), item.get("created_at") or "", str(item.get("id"))))

        messages = []
        last_date = None
        for item in rows[-100:]:
            created_at = item.get("created_at") or now_full()
            date_part = created_at.split(" ")[0]
            date_label = None
            if date_part != last_date:
                today = datetime.now().strftime("%Y-%m-%d")
                date_label = "Сегодня" if date_part == today else date_part
                last_date = date_part

            user_data = users.get(item.get("user"), {})
            role = user_data.get("role") or ""
            reply = by_id.get(str(item.get("reply_to"))) if item.get("reply_to") else None
            username = item.get("user") or ""
            messages.append(
                {
                    "id": str(item.get("id")),
                    "user": username,
                    "message": item.get("message"),
                    "time": item.get("time"),
                    "avatar": user_data.get("avatar") or "default.jpg",
                    "file": item.get("file"),
                    "file_name": item.get("file_name"),
                    "message_type": item.get("message_type") or "text",
                    "pinned": item.get("pinned") or 0,
                    "edited_at": item.get("edited_at"),
                    "date_label": date_label,
                    "reply_to": item.get("reply_to"),
                    "likes": item.get("likes") or 0,
                    "fires": item.get("fires") or 0,
                    "hearts": item.get("hearts") or 0,
                    "is_admin": role == "Админ" or username.lower() in ("admin", "corleone", "don7"),
                    "reply_user": reply.get("user") if reply else None,
                    "reply_message": reply.get("message") if reply else None,
                }
            )
        return messages

    @staticmethod
    def edit_message(message_id, user, message):
        if FIREBASE_DB:
            ref = FIREBASE_DB.collection("chat").document(message_id)
            doc = ref.get()
            if doc.exists and doc.to_dict().get("user") == user:
                ref.set({"message": message, "edited_at": now_time()}, merge=True)
            return

        conn = db()
        c = conn.cursor()
        c.execute(
            "UPDATE chat SET message=?, edited_at=? WHERE id=? AND user=?",
            (message, now_time(), message_id, user),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def react_message(message_id, reaction):
        columns = {"like": "likes", "fire": "fires", "heart": "hearts"}
        column = columns.get(reaction)
        if not column:
            return

        if FIREBASE_DB:
            FIREBASE_DB.collection("chat").document(message_id).set(
                {column: FIRESTORE.Increment(1)},
                merge=True,
            )
            return

        conn = db()
        c = conn.cursor()
        c.execute(f"UPDATE chat SET {column} = COALESCE({column}, 0) + 1 WHERE id=?", (message_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def toggle_pin(message_id):
        if FIREBASE_DB:
            ref = FIREBASE_DB.collection("chat").document(message_id)
            doc = ref.get()
            if doc.exists:
                current = doc.to_dict().get("pinned") or 0
                ref.set({"pinned": 0 if current else 1}, merge=True)
            return

        conn = db()
        c = conn.cursor()
        c.execute("SELECT pinned FROM chat WHERE id=?", (message_id,))
        result = c.fetchone()
        if result:
            c.execute("UPDATE chat SET pinned=? WHERE id=?", (0 if result[0] else 1, message_id))
            conn.commit()
        conn.close()


def image_src(value):
    if not value:
        return ""
    if value.startswith("data:") or value.startswith("http://") or value.startswith("https://"):
        return value
    return f"/static/img/{value}"


app.jinja_env.filters["image_src"] = image_src


SECTION_LABELS = {
    "pmr_exchange": "ПМР — Обменники",
    "pmr_shop": "ПМР — Магазины",
    "md_exchange": "Молдова — Обменники",
    "md_shop": "Магазины-Молдова",
    "services": "Разные услуги",
}


def section_label(value):
    return SECTION_LABELS.get(value, value)


app.jinja_env.filters["section_label"] = section_label


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def home():
    dynamic_cards = Store.cards()
    default_cards = Store.default_cards()
    cards_by_section = {}
    default_cards_by_section = {}
    for card in dynamic_cards:
        cards_by_section.setdefault(card["section"], []).append(card)
    for card in default_cards:
        default_cards_by_section.setdefault(card["section"], []).append(card)

    return render_template(
        "index.html",
        registered_count=148 + Store.users_count(),
        service_count=len(default_cards) + len(dynamic_cards),
        cards_by_section=cards_by_section,
        default_cards_by_section=default_cards_by_section,
        banner_src=Store.get_setting("hero_banner", "banner.jpg"),
        banner_link=Store.get_setting("hero_banner_link", "https://t.me/doncrln"),
        storage_mode="firebase" if Store.using_firebase() else "sqlite",
    )


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect("/admin/login")

    if request.method == "POST":
        if request.form.get("form_type") == "banner":
            banner_src_value = save_admin_image(request.files.get("banner"), "banner")
            if banner_src_value:
                Store.set_setting("hero_banner", banner_src_value)
            banner_link_value = clean_external_link(request.form.get("banner_link")) or "https://t.me/doncrln"
            Store.set_setting("hero_banner_link", banner_link_value)
            return redirect("/admin")

        section = request.form.get("section", "services")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        link = clean_external_link(request.form.get("link")) or "#"
        image_src_value = save_admin_image(request.files.get("image"), "card")

        if title and description and image_src_value:
            Store.add_card(section, title, description, link, image_src_value)

        return redirect("/admin")

    return render_template(
        "admin.html",
        cards=Store.all_admin_cards(),
        banner_src=Store.get_setting("hero_banner", "banner.jpg"),
        banner_link=Store.get_setting("hero_banner_link", "https://t.me/doncrln"),
    )


@app.route("/admin/edit/<card_id>", methods=["GET", "POST"])
def admin_edit(card_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    card = Store.get_card(card_id)
    if not card:
        return redirect("/admin")

    if request.method == "POST":
        section = request.form.get("section", "services")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        link = clean_external_link(request.form.get("link")) or "#"
        image_src_value = save_admin_image(request.files.get("image"), "card")

        if title and description:
            Store.update_card(card_id, section, title, description, link, image_src_value)
            return redirect("/admin")

    return render_template("admin_edit.html", card=card)


@app.route("/admin/delete/<card_id>", methods=["POST"])
def admin_delete(card_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    Store.delete_card(card_id)
    return redirect("/admin")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session.permanent = True
            session["admin"] = True
            return redirect("/admin")
        error = "Неверный пароль"

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/")


@app.route("/chat")
def chat():
    avatar = "default.jpg"
    if "user" in session:
        avatar = Store.user_avatar(session["user"])

    return render_template("chat.html", messages=Store.messages(), avatar=avatar)


@app.route("/send", methods=["POST"])
def send():
    if "user" not in session:
        return redirect("/login")

    message = request.form.get("message", "").strip()
    voice = request.files.get("voice")
    attachment = request.files.get("attachment")
    reply_to = request.form.get("reply_to") or None
    user = session["user"]

    file_name = None
    original_name = None
    message_type = "text"

    if voice and voice.filename:
        file_name, original_name = save_uploaded_file(voice, UPLOAD_FOLDER, user)
        message_type = "voice"
        original_name = original_name or "voice-message.webm"
    elif attachment and attachment.filename:
        file_name, original_name = save_uploaded_file(attachment, UPLOAD_FOLDER, user)
        message_type = "file"

    if not message and not file_name:
        return redirect("/chat")

    Store.add_message(user, message, file_name, original_name, message_type, reply_to)
    return redirect("/chat")


@app.route("/chat/react/<message_id>/<reaction>", methods=["POST"])
def react_message(message_id, reaction):
    if "user" not in session:
        return redirect("/login")

    Store.react_message(message_id, reaction)
    return redirect("/chat")


@app.route("/chat/edit/<message_id>", methods=["POST"])
def edit_message(message_id):
    if "user" not in session:
        return redirect("/login")

    message = request.form.get("message", "").strip()
    if message:
        Store.edit_message(message_id, session["user"], message)

    return redirect("/chat")


@app.route("/chat/pin/<message_id>", methods=["POST"])
def pin_message(message_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    Store.toggle_pin(message_id)
    return redirect("/chat")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = request.form["username"].strip()
        password = request.form["password"]

        if Store.create_user(user, password):
            session.permanent = True
            session["user"] = user
            return redirect("/")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"].strip()
        password = request.form["password"]

        if Store.check_user(user, password):
            session.permanent = True
            session["user"] = user
            return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/upload_avatar", methods=["POST"])
def upload_avatar():
    if "user" not in session:
        return redirect("/login")

    filename, _ = save_uploaded_file(request.files.get("avatar"), AVATAR_FOLDER, session["user"])
    if filename:
        Store.update_avatar(session["user"], filename)

    return redirect("/chat")


if __name__ == "__main__":
    print("SERVER START")
    print("STORAGE:", "Firebase" if Store.using_firebase() else "SQLite fallback")
    app.run(debug=True)
