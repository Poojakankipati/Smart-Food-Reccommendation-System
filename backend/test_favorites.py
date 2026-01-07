import os
import sqlite3
import json

from app import app

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'foodreco.db')

TEST_MOBILE = '+919999000111'
TEST_ITEM = 'Idly (3)'

def db_rows():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT user_mobile, item_name, created_at FROM favorites WHERE user_mobile = ?', (TEST_MOBILE,))
    rows = cur.fetchall()
    conn.close()
    return rows

def main():
    client = app.test_client()
    print('Initial DB rows for', TEST_MOBILE, db_rows())

    # Add favorite
    r = client.post('/api/favorites', json={'mobile': TEST_MOBILE, 'item': TEST_ITEM})
    print('POST /api/favorites', r.status_code, r.get_json())
    print('After POST DB rows:', db_rows())

    # Get favorites
    r = client.get('/api/favorites', query_string={'mobile': TEST_MOBILE})
    print('GET /api/favorites', r.status_code, r.get_json())

    # Remove favorite
    r = client.delete('/api/favorites', json={'mobile': TEST_MOBILE, 'item': TEST_ITEM})
    print('DELETE /api/favorites', r.status_code, r.get_json())
    print('After DELETE DB rows:', db_rows())
    # Add again and delete using query params
    r = client.post('/api/favorites', json={'mobile': TEST_MOBILE, 'item': TEST_ITEM})
    print('Re-POST', r.status_code, r.get_json())
    r = client.delete('/api/favorites?mobile='+TEST_MOBILE+'&item='+TEST_ITEM)
    print('DELETE via query params', r.status_code, r.get_json())
    print('Final DB rows:', db_rows())

if __name__ == '__main__':
    main()
