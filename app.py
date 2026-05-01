from datetime import datetime
import os
import sqlite3

from flask import Flask, redirect, render_template, request, session
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "secret123"
ADMIN_PASSWORD = "148corleone"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
AVATAR_FOLDER = os.path.join(BASE_DIR, "static", "img")


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

    conn = db()
    c = conn.cursor()
    ensure_column(c, "chat", "file", "TEXT")
    ensure_column(c, "chat", "file_name", "TEXT")
    ensure_column(c, "chat", "message_type", "TEXT DEFAULT 'text'")
    ensure_column(c, "chat", "pinned", "INTEGER DEFAULT 0")
    ensure_column(c, "chat", "edited_at", "TEXT")
    ensure_column(c, "chat", "created_at", "TEXT")
    ensure_column(c, "chat", "reply_to", "INTEGER")
    ensure_column(c, "chat", "likes", "INTEGER DEFAULT 0")
    ensure_column(c, "chat", "fires", "INTEGER DEFAULT 0")
    ensure_column(c, "chat", "hearts", "INTEGER DEFAULT 0")
    c.execute("UPDATE users SET avatar='default.jpg' WHERE avatar IS NULL OR avatar='default.png'")
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
    conn.commit()
    conn.close()


def save_uploaded_file(file, folder, prefix):
    if not file or not file.filename:
        return None, None

    original_name = secure_filename(file.filename)
    if not original_name:
        return None, None

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"{prefix}_{timestamp}_{original_name}"
    file.save(os.path.join(folder, filename))

    return filename, original_name


init_storage()


@app.route("/")
def home():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    registered_count = 148 + c.fetchone()[0]
    c.execute("SELECT section, title, description, image, link FROM cards ORDER BY id DESC")
    dynamic_cards = c.fetchall()
    conn.close()

    cards_by_section = {}
    for section, title, description, image, link in dynamic_cards:
        cards_by_section.setdefault(section, []).append(
            {
                "title": title,
                "description": description,
                "image": image,
                "link": link,
            }
        )

    service_count = 5 + len(dynamic_cards)

    return render_template(
        "index.html",
        registered_count=registered_count,
        service_count=service_count,
        cards_by_section=cards_by_section,
    )


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect("/admin/login")

    if request.method == "POST":
        section = request.form.get("section", "services")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        link = request.form.get("link", "").strip()
        image_file = request.files.get("image")
        image, _ = save_uploaded_file(image_file, AVATAR_FOLDER, "card")

        if title and description and link and image:
            conn = db()
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO cards (section, title, description, image, link, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    section,
                    title,
                    description,
                    image,
                    link,
                    datetime.now().strftime("%d-%m-%Y %H:%M"),
                ),
            )
            conn.commit()
            conn.close()

        return redirect("/admin")

    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, section, title, description, image, link FROM cards ORDER BY id DESC")
    cards = c.fetchall()
    conn.close()

    return render_template("admin.html", cards=cards)


@app.route("/admin/edit/<int:card_id>", methods=["GET", "POST"])
def admin_edit(card_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = db()
    c = conn.cursor()

    if request.method == "POST":
        section = request.form.get("section", "services")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        link = request.form.get("link", "").strip()
        image_file = request.files.get("image")
        image, _ = save_uploaded_file(image_file, AVATAR_FOLDER, "card")

        if title and description and link:
            if image:
                c.execute(
                    """
                    UPDATE cards
                    SET section=?, title=?, description=?, link=?, image=?
                    WHERE id=?
                    """,
                    (section, title, description, link, image, card_id),
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
            return redirect("/admin")

    c.execute("SELECT id, section, title, description, image, link FROM cards WHERE id=?", (card_id,))
    card = c.fetchone()
    conn.close()

    if not card:
        return redirect("/admin")

    return render_template("admin_edit.html", card=card)


@app.route("/admin/delete/<int:card_id>", methods=["POST"])
def admin_delete(card_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM cards WHERE id=?", (card_id,))
    conn.commit()
    conn.close()

    return redirect("/admin")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
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
    conn = db()
    c = conn.cursor()
    c.execute(
        """
        SELECT chat.id, chat.user, chat.message, chat.time, users.avatar,
               chat.file, chat.file_name, chat.message_type, chat.pinned, chat.edited_at,
               chat.created_at, chat.reply_to, chat.likes, chat.fires, chat.hearts,
               users.role, parent.user, parent.message
        FROM chat
        LEFT JOIN users ON chat.user = users.username
        LEFT JOIN chat AS parent ON chat.reply_to = parent.id
        ORDER BY chat.pinned DESC, chat.id ASC
        LIMIT 100
        """
    )
    rows = c.fetchall()

    avatar = "default.jpg"
    if "user" in session:
        c.execute("SELECT avatar FROM users WHERE username=?", (session["user"],))
        result = c.fetchone()
        if result and result[0]:
            avatar = result[0]

    conn.close()

    messages = []
    last_date = None
    for row in rows:
        created_at = row[10] or datetime.now().strftime("%Y-%m-%d %H:%M")
        date_part = created_at.split(" ")[0]
        date_label = None
        if date_part != last_date:
            today = datetime.now().strftime("%Y-%m-%d")
            date_label = "Сегодня" if date_part == today else date_part
            last_date = date_part

        role = row[15] or ""
        is_admin = role == "Админ" or row[1].lower() in ("admin", "corleone", "don7")
        messages.append(
            {
                "id": row[0],
                "user": row[1],
                "message": row[2],
                "time": row[3],
                "avatar": row[4] or "default.jpg",
                "file": row[5],
                "file_name": row[6],
                "message_type": row[7],
                "pinned": row[8],
                "edited_at": row[9],
                "date_label": date_label,
                "reply_to": row[11],
                "likes": row[12] or 0,
                "fires": row[13] or 0,
                "hearts": row[14] or 0,
                "is_admin": is_admin,
                "reply_user": row[16],
                "reply_message": row[17],
            }
        )

    return render_template("chat.html", messages=messages, avatar=avatar)


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

    conn = db()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO chat (user, message, time, file, file_name, message_type, created_at, reply_to)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user,
            message,
            datetime.now().strftime("%H:%M"),
            file_name,
            original_name,
            message_type,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            reply_to,
        ),
    )
    conn.commit()
    conn.close()

    return redirect("/chat")


@app.route("/chat/react/<int:message_id>/<reaction>", methods=["POST"])
def react_message(message_id, reaction):
    if "user" not in session:
        return redirect("/login")

    columns = {
        "like": "likes",
        "fire": "fires",
        "heart": "hearts",
    }
    column = columns.get(reaction)
    if not column:
        return redirect("/chat")

    conn = db()
    c = conn.cursor()
    c.execute(f"UPDATE chat SET {column} = COALESCE({column}, 0) + 1 WHERE id=?", (message_id,))
    conn.commit()
    conn.close()

    return redirect("/chat")


@app.route("/chat/edit/<int:message_id>", methods=["POST"])
def edit_message(message_id):
    if "user" not in session:
        return redirect("/login")

    message = request.form.get("message", "").strip()
    if not message:
        return redirect("/chat")

    conn = db()
    c = conn.cursor()
    c.execute(
        """
        UPDATE chat
        SET message=?, edited_at=?
        WHERE id=? AND user=?
        """,
        (message, datetime.now().strftime("%H:%M"), message_id, session["user"]),
    )
    conn.commit()
    conn.close()

    return redirect("/chat")


@app.route("/chat/pin/<int:message_id>", methods=["POST"])
def pin_message(message_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    conn = db()
    c = conn.cursor()
    c.execute("SELECT pinned FROM chat WHERE id=?", (message_id,))
    result = c.fetchone()

    if result:
        next_state = 0 if result[0] else 1
        c.execute("UPDATE chat SET pinned=? WHERE id=?", (next_state, message_id))
        conn.commit()

    conn.close()

    return redirect("/chat")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = request.form["username"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (username, password, avatar, created_at) VALUES (?, ?, ?, ?)",
            (user, password, "default.jpg", datetime.now().strftime("%d-%m-%Y %H:%M")),
        )
        conn.commit()
        conn.close()

        session["user"] = user
        return redirect("/")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, password))
        result = c.fetchone()
        conn.close()

        if result:
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

    file = request.files.get("avatar")
    filename, _ = save_uploaded_file(file, AVATAR_FOLDER, session["user"])

    if filename:
        conn = db()
        c = conn.cursor()
        c.execute("UPDATE users SET avatar=? WHERE username=?", (filename, session["user"]))
        conn.commit()
        conn.close()

    return redirect("/chat")


if __name__ == "__main__":
    print("SERVER START")
    app.run(debug=True)
