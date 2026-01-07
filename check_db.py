import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), 'foodreco.db')
print('DB path:', DB)
print('Exists:', os.path.exists(DB))
if not os.path.exists(DB):
    raise SystemExit('DB not found')
conn = sqlite3.connect(DB)
cur = conn.cursor()
rows = cur.execute('SELECT id,name,mobile,is_admin FROM users').fetchall()
print('Users:')
for r in rows:
    print(r)
conn.close()
