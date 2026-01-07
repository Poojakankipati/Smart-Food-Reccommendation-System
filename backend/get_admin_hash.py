import os
import sqlite3
from werkzeug.security import check_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'foodreco.db')

def main():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT password_hash FROM users WHERE mobile = ?', ('+917671953326',)).fetchone()
    if not row:
        print('NOT_FOUND')
        return
    h = row[0]
    print('HASH:' + h)
    print('MATCHES_DEFAULT_ADMINPASS:' + str(check_password_hash(h, 'adminpass')))

if __name__ == '__main__':
    main()
