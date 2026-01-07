import os
import sqlite3
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'foodreco.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        mobile TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        otp TEXT,
        otp_expiry TIMESTAMP
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        name TEXT,
        mobile TEXT,
        payment TEXT,
        pre_order INTEGER,
        delivery_date TEXT,
        delivery_time TEXT,
        items TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_mobile TEXT,
        user_name TEXT,
        item_name TEXT,
        rating INTEGER,
        review TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    # Favorites table: user_mobile -> item_name
    cur.execute('''
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_mobile TEXT,
        item_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_mobile, item_name)
    )
    ''')
    # Ensure 'name' column exists for older orders DB
    cur.execute("PRAGMA table_info(orders)")
    cols = [r[1] for r in cur.fetchall()]
    if 'name' not in cols:
        try:
            cur.execute('ALTER TABLE orders ADD COLUMN name TEXT')
        except Exception:
            pass
    # Ensure 'name' column exists for older DBs
    cur.execute("PRAGMA table_info(orders)")
    cols = [r[1] for r in cur.fetchall()]
    if 'name' not in cols:
        try:
            cur.execute('ALTER TABLE orders ADD COLUMN name TEXT')
        except Exception:
            pass
    # Insert default admin (mobile: 9999999999, password: adminpass)
    try:
        cur.execute('INSERT INTO users (name, mobile, password_hash, is_admin) VALUES (?, ?, ?, 1)',
                    ('Administrator', '+917671953326', generate_password_hash('adminpass')))
    except sqlite3.IntegrityError:
        pass
    # Normalize existing users: prefix +91 for 10-digit mobiles
    try:
        cur.execute('SELECT id, mobile FROM users')
        rows = cur.fetchall()
        for r in rows:
            uid, mob = r[0], r[1]
            if not mob:
                continue
            digits = ''.join(ch for ch in str(mob) if ch.isdigit())
            if len(digits) == 10:
                try:
                    cur.execute('UPDATE users SET mobile = ? WHERE id = ?', ('+91'+digits, uid))
                except Exception:
                    pass
    except Exception:
        pass
    # Ensure 'otp' and 'otp_expiry' columns exist for older DBs
    cur.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in cur.fetchall()]
    if 'otp' not in cols:
        try:
            cur.execute('ALTER TABLE users ADD COLUMN otp TEXT')
        except Exception:
            pass
    if 'otp_expiry' not in cols:
        try:
            cur.execute('ALTER TABLE users ADD COLUMN otp_expiry TIMESTAMP')
        except Exception:
            pass
    conn.commit()
    conn.close()
    print('Initialized database at', DB_PATH)

if __name__ == '__main__':
    init_db()
