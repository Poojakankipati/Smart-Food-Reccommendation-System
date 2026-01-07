import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

NEW_PASSWORD = "1234"
ADMIN_MOBILE = "+917671953326"

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'foodreco.db')

def main():
    conn = sqlite3.connect(DB_PATH)
    with conn:
        conn.execute('UPDATE users SET password_hash = ? WHERE mobile = ?',
                     (generate_password_hash(NEW_PASSWORD), ADMIN_MOBILE))
    row = sqlite3.connect(DB_PATH).execute('SELECT password_hash FROM users WHERE mobile = ?', (ADMIN_MOBILE,)).fetchone()
    if not row:
        print('Admin account not found for', ADMIN_MOBILE)
        return
    h = row[0]
    ok = check_password_hash(h, NEW_PASSWORD)
    print(f'Updated admin password for {ADMIN_MOBILE}. Verified: {ok}')

if __name__ == '__main__':
    main()
