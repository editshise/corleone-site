from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"


@app.route('/')
def home():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT * FROM chat ORDER BY rowid DESC LIMIT 12")
    messages = c.fetchall()

    conn.close()

    return render_template('index.html', messages=messages[::-1])


@app.route('/send', methods=['POST'])
def send():
    if 'user' not in session:
        return redirect('/login')

    message = request.form['message']
    user = session['user']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("INSERT INTO chat (user, message) VALUES (?, ?)", (user, message))
    conn.commit()
    conn.close()

    return redirect('/')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, password))
        conn.commit()
        conn.close()

        return redirect('/login')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, password))
        result = c.fetchone()
        conn.close()

        if result:
            session['user'] = user
            return redirect('/')

    return render_template('login.html')
