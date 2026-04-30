from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "secret123"


def db():
    return sqlite3.connect("database.db")


# главная
@app.route('/')
def home():
    conn = db()
    c = conn.cursor()

    c.execute("""
        SELECT chat.user, chat.message, chat.time, users.avatar
        FROM chat
        LEFT JOIN users ON chat.user = users.username
        ORDER BY chat.id ASC
        LIMIT 50
    """)

    messages = c.fetchall()
    conn.close()

    return render_template('index.html', messages=messages)


# отправка сообщения
@app.route('/send', methods=['POST'])
def send():
    if 'user' not in session:
        return redirect('/login')

    message = request.form['message']
    user = session['user']

    conn = db()
    c = conn.cursor()

    c.execute(
        "INSERT INTO chat (user, message, time) VALUES (?, ?, ?)",
        (user, message, datetime.now().strftime("%H:%M"))
    )

    conn.commit()
    conn.close()

    return redirect('/')


# регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username']
        password = request.form['password']

        conn = db()
        c = conn.cursor()

        c.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
            (user, password, datetime.now().strftime("%d-%m-%Y %H:%M"))
        )

        conn.commit()
        conn.close()

        session['user'] = user
        return redirect('/')

    return render_template('register.html')


# вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        password = request.form['password']

        conn = db()
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, password))
        result = c.fetchone()

        conn.close()

        if result:
            session['user'] = user
            return redirect('/')

    return render_template('login.html')


# выход
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# аватар
@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'user' not in session:
        return redirect('/login')

    file = request.files['avatar']

    if file:
        filename = session['user'] + ".png"
        path = os.path.join("static/img", filename)
        file.save(path)

        conn = db()
        c = conn.cursor()
        c.execute("UPDATE users SET avatar=? WHERE username=?", (filename, session['user']))
        conn.commit()
        conn.close()

    return redirect('/')

if __name__ == "__main__":
    print("SERVER START")
    app.run(debug=True)
