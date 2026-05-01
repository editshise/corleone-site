from datetime import datetime, timedelta
import os

from flask import Flask, redirect, render_template, request, session
from werkzeug.utils import secure_filename

import firebase_admin
from firebase_admin import credentials, firestore

# 🔑 Firebase
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db_firestore = firestore.client()

app = Flask(__name__)
app.secret_key = "secret123"
app.permanent_session_lifetime = timedelta(days=30)

ADMIN_PASSWORD = "148corleone"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
AVATAR_FOLDER = os.path.join(BASE_DIR, "static", "img")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)


def save_uploaded_file(file, folder, prefix):
    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"{prefix}_{timestamp}_{filename}"

    file.save(os.path.join(folder, filename))
    return filename


# =========================
# 🔥 ГЛАВНАЯ (КАРТОЧКИ)
# =========================
@app.route("/")
def home():
    cards_ref = db_firestore.collection("cards") \
        .order_by("created_at", direction=firestore.Query.DESCENDING) \
        .stream()

    cards_by_section = {}

    for doc in cards_ref:
        data = doc.to_dict()
        section = data.get("section")

        cards_by_section.setdefault(section, []).append({
            "title": data.get("title"),
            "description": data.get("description"),
            "image": data.get("image"),
            "link": data.get("link"),
        })

    return render_template(
        "index.html",
        registered_count=150,
        service_count=5,
        cards_by_section=cards_by_section,
    )


# =========================
# 🔐 АДМИНКА КАРТОЧЕК
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect("/admin/login")

    if request.method == "POST":
        section = request.form.get("section", "services")
        title = request.form.get("title")
        description = request.form.get("description")
        link = request.form.get("link")
        image_file = request.files.get("image")

        image = save_uploaded_file(image_file, AVATAR_FOLDER, "card")

        if title and description and link and image:
            db_firestore.collection("cards").add({
                "section": section,
                "title": title,
                "description": description,
                "image": image,
                "link": link,
                "created_at": datetime.now()
            })

        return redirect("/admin")

    cards = db_firestore.collection("cards") \
        .order_by("created_at", direction=firestore.Query.DESCENDING) \
        .stream()

    cards_list = []
    for doc in cards:
        data = doc.to_dict()
        data["id"] = doc.id
        cards_list.append(data)

    return render_template("admin.html", cards=cards_list)


@app.route("/admin/delete/<card_id>", methods=["POST"])
def delete(card_id):
    if not session.get("admin"):
        return redirect("/admin/login")

    db_firestore.collection("cards").document(card_id).delete()
    return redirect("/admin")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/")


# =========================
# 💬 ЧАТ (Firebase)
# =========================
@app.route("/chat")
def chat():
    messages_ref = db_firestore.collection("messages") \
        .order_by("created_at") \
        .limit(100) \
        .stream()

    messages = []

    for doc in messages_ref:
        data = doc.to_dict()

        messages.append({
            "id": doc.id,
            "user": data.get("user"),
            "message": data.get("message"),
            "time": data.get("time"),
            "avatar": data.get("avatar", "default.jpg"),
            "file": data.get("file"),
            "file_name": data.get("file_name"),
            "message_type": data.get("message_type", "text"),
            "likes": data.get("likes", 0),
            "fires": data.get("fires", 0),
            "hearts": data.get("hearts", 0),
        })

    avatar = "default.jpg"

    return render_template("chat.html", messages=messages, avatar=avatar)


@app.route("/send", methods=["POST"])
def send():
    if "user" not in session:
        return redirect("/login")

    message = request.form.get("message", "").strip()
    user = session["user"]

    if not message:
        return redirect("/chat")

    db_firestore.collection("messages").add({
        "user": user,
        "message": message,
        "time": datetime.now().strftime("%H:%M"),
        "created_at": datetime.now(),
        "likes": 0,
        "fires": 0,
        "hearts": 0
    })

    return redirect("/chat")


@app.route("/chat/react/<message_id>/<reaction>", methods=["POST"])
def react_message(message_id, reaction):
    if "user" not in session:
        return redirect("/login")

    doc_ref = db_firestore.collection("messages").document(message_id)

    field = {
        "like": "likes",
        "fire": "fires",
        "heart": "hearts"
    }.get(reaction)

    if field:
        doc = doc_ref.get()
        current = doc.to_dict().get(field, 0)
        doc_ref.update({field: current + 1})

    return redirect("/chat")


# =========================
# 👤 ПРОСТАЯ АВТОРИЗАЦИЯ (пока локально)
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        session["user"] = request.form["username"]
        return redirect("/")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["user"] = request.form["username"]
        return redirect("/")
    return render_template("login.html")


@app.route("/logout_user")
def logout_user():
    session.clear()
    return redirect("/")
    

if __name__ == "__main__":
    app.run(debug=True)
