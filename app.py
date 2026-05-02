from datetime import datetime, timedelta
import os
import json

from flask import Flask, redirect, render_template, request, session
from werkzeug.utils import secure_filename

import firebase_admin
from firebase_admin import credentials, firestore

# 🔥 Firebase через ENV (Render)
firebase_key = json.loads(os.environ.get("FIREBASE_KEY"))

cred = credentials.Certificate(firebase_key)
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
    filename = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    file.save(os.path.join(folder, filename))
    return filename


# =======================
# ГЛАВНАЯ (без ошибок)
# =======================
@app.route("/")
def home():
    cards_docs = list(db_firestore.collection("cards").stream())

    cards_by_section = {}

    for doc in cards_docs:
        data = doc.to_dict()
        section = data.get("section", "services")

        cards_by_section.setdefault(section, []).append({
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "image": data.get("image", "default.jpg"),
            "link": data.get("link", ""),
        })

    registered_count = 150  # временно
    service_count = 5 + len(cards_docs)

    return render_template(
        "index.html",
        registered_count=registered_count,
        service_count=service_count,
        cards_by_section=cards_by_section,
    )


# =======================
# АДМИНКА
# =======================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect("/admin/login")

    if request.method == "POST":
        section = request.form.get("section", "services")
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        link = request.form.get("link", "")
        image_file = request.files.get("image")

        image = save_uploaded_file(image_file, AVATAR_FOLDER, "card")

        if not image:
            image = "default.jpg"

        if title and description and link:
            db_firestore.collection("cards").add({
                "section": section,
                "title": title,
                "description": description,
                "image": image,
                "link": link,
                "created_at": datetime.now()
            })

        return redirect("/admin")

    cards = db_firestore.collection("cards").stream()

    cards_list = []
    for doc in cards:
        data = doc.to_dict()
        data["id"] = doc.id
        cards_list.append(data)

    return render_template("admin.html", cards=cards_list)


@app.route("/admin/delete/<card_id>", methods=["POST"])
def delete(card_id):
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


# =======================
# ЧАТ (исправленный)
# =======================
@app.route("/chat")
def chat():
    messages = db_firestore.collection("messages") \
        .order_by("created_at") \
        .limit(100) \
        .stream()

    result = []

    for doc in messages:
        data = doc.to_dict()

        result.append({
            "id": doc.id,
            "user": data.get("user", ""),
            "message": data.get("message", ""),
            "time": data.get("time", ""),
            "avatar": data.get("avatar", "default.jpg"),
            "likes": data.get("likes", 0),
            "fires": data.get("fires", 0),
            "hearts": data.get("hearts", 0),
        })

    return render_template("chat.html", messages=result, avatar="default.jpg")


@app.route("/send", methods=["POST"])
def send():
    if "user" not in session:
        return redirect("/login")

    message = request.form.get("message", "").strip()
    user = session["user"]

    if message:
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


# =======================
# ЛОГИН
# =======================
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
