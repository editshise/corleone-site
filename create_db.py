import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

# пользователи
c.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    password TEXT,
    avatar TEXT DEFAULT 'default.png',
    role TEXT DEFAULT 'Пользователь',
    created_at TEXT
)
""")

# чат
c.execute("""
CREATE TABLE chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT,
    message TEXT,
    time TEXT
)
""")

conn.commit()
conn.close()

print("База пересоздана")
