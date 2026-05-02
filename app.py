from datetime import datetime, timedelta
import os
import json

from flask import Flask, redirect, render_template, request, session

import firebase_admin
from firebase_admin import credentials, firestore, storage

# Firebase через ENV (Render)
firebase_key = json.loads(os.environ.get("FIREBASE_KEY"))

cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred, {
    'storageBucket': f"{firebase_key['project_id']}.appspot.com"
})

db_firestore = firestore.client()

app = Flask(__name__)
app.secret_key = "secret123"
app.permanent_session_lifetime = timedelta(days=30)

ADMIN_PASSWORD = "148corleone"


# загрузка в Firebase Storage
def upload_to_firebase(file):
    if not file:
        return None

    bucket = storage.bucket()
    filename = f"cards/{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"

    blob = bucket.blob(filename)
    blob.upload_from_file(file)
    blob.make_public()

    return blob.public_url


# главная
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
            "image": data.get("image", ""),
            "link": data.get("link", ""),
        })

    return render_template(
        "index.html",
        registered_count=150,
        service_count=5 + len(cards_docs),
        cards_by_section=cards_by_section,
    )


# админка
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

        image = upload_to_firebase(image_file)

        if title and description and link:
            db_firestore.collection("cards").add({
                "section": section,
                "title": title,
                "description": description,
                "image": image or "",
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


# чат
@app.route("/chat")
def chat():
    messages = db_firestore.collection("messages") \
        .order_by("created_at") \
        .limit(100) \
        .stream()

    result = []

    for doc in messages:
        data = doc.to_dict()
        data["id"] = doc.id
        result.append(data)

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
            "created_at": datetime.now()
        })

    return redirect("/chat")


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
