import os
import sqlite3
import random
import datetime
from flask import Flask, request, redirect, render_template, session, flash, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# Optional: load environment variables from .env in development
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def _digits_only(s):
    return ''.join(ch for ch in (s or '') if ch.isdigit())

def normalize_mobile(m):
    """Normalize mobile numbers: if 10 digits, prefix with +91; otherwise ensure leading + and digits only."""
    if not m:
        return m
    digits = _digits_only(m)
    if len(digits) == 10:
        return '+91' + digits
    if len(digits) > 10:
        return '+' + digits
    return digits

# Resolve project paths
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'foodreco.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    conn = get_db()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_mobile TEXT,
                message TEXT,
                order_id TEXT,
                eta_minutes INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                read INTEGER DEFAULT 0
            )
        ''')

# Ensure notifications table exists on startup
ensure_tables()

# Runtime set to track unique logged-in member mobiles (in-memory)
LOGGED_IN_MEMBERS = set()

# Serve frontend templates and static files from the `frontend` folder
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'frontend'),
    static_url_path='',  # serve frontend files at web root (e.g. /images/...)
    template_folder=os.path.join(BASE_DIR, 'frontend', 'templates')
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.permanent_session_lifetime = datetime.timedelta(days=7)  # Session lasts 7 days


@app.route('/')
def index():
    # If already logged in server-side, redirect to appropriate page
    if session.get('user_id'):
        if session.get('is_admin'):
            return redirect(url_for('admin_html'))
        else:
            return redirect(url_for('about_html'))
    return render_template('login.html')


@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    mobile = normalize_mobile(request.form.get('mobile'))
    password = request.form.get('password')
    if not (name and mobile and password):
        flash('Missing required fields')
        return redirect(url_for('index'))
    conn = get_db()
    try:
        with conn:
            conn.execute(
                'INSERT INTO users (name, mobile, password_hash, is_admin) VALUES (?, ?, ?, 0)',
                (name, mobile, generate_password_hash(password))
            )
    except sqlite3.IntegrityError:
        flash('Mobile number already registered')
        return redirect(url_for('index'))
    flash('Account created. Please login.')
    return redirect(url_for('index'))


@app.route('/login', methods=['POST'])
def login():
    mobile = normalize_mobile(request.form.get('mobile'))
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    print(f"[login] attempt from {request.remote_addr} mobile={mobile} role={role}")
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE mobile = ?', (mobile,)).fetchone()
    print(f"[login] db_user={'found' if user else 'none'}")
    if not user:
        print("[login] no such user:", mobile)
        flash("Account doesn't exist")
        return redirect(url_for('index'))

    # Reject admin accounts when logging in via the user form, and reject non-admins on admin form
    try:
        is_admin_flag = bool(user['is_admin'])
    except Exception:
        is_admin_flag = False
    if role == 'user' and is_admin_flag:
        print(f"[login] account type mismatch: admin used user form: {mobile}")
        flash("Account doesn't exist")
        return redirect(url_for('index'))
    if role == 'admin' and not is_admin_flag:
        print(f"[login] account type mismatch: user used admin form: {mobile}")
        flash("Account doesn't exist")
        return redirect(url_for('index'))

    if not check_password_hash(user['password_hash'], password):
        print("[login] wrong password for:", mobile)
        flash('Invalid credentials')
        return redirect(url_for('index'))

    session['user_id'] = user['id']
    session['is_admin'] = bool(user['is_admin'])
    session.permanent = True  # Make session persistent
    # Track unique logged-in members (in-memory runtime telemetry)
    try:
        LOGGED_IN_MEMBERS.add(mobile)
        print(f"[members] unique logged-in count: {len(LOGGED_IN_MEMBERS)}")
    except Exception:
        pass
    # Redirect to after_login helper which sets localStorage then navigates
    if session['is_admin']:
        return redirect(url_for('after_login', mobile=mobile, role='admin'))
    else:
        print("[login] user authenticated:", mobile)
        return redirect(url_for('after_login', mobile=mobile, role='user'))


@app.route('/after_login')
def after_login():
    # This returns a small HTML page that sets localStorage then redirects
    mobile = request.args.get('mobile', '')
    role = request.args.get('role', 'user')
    # fetch user name from DB (if available)
    name = ''
    try:
        conn = get_db()
        row = conn.execute('SELECT name FROM users WHERE mobile = ?', (mobile,)).fetchone()
        if row:
            name = row['name']
    except Exception:
        name = ''
    # Use absolute URLs so the browser always navigates to the running server
    target = url_for('admin_html', _external=True) if role == 'admin' else url_for('about_html', _external=True)
    print('[after_login] session:', dict(session))
    return f"""<!doctype html>
<html>
    <head>
        <meta charset="utf-8">
        <title>Redirecting...</title>
    </head>
    <body>
        <script>
            localStorage.setItem('loggedUser', '{name}');
            localStorage.setItem('role', '{role}');
            localStorage.setItem('loggedUserMobile', '{mobile}');
            window.location.href = '{target}';
        </script>
    </body>
</html>
"""


@app.route('/about.html')
def about_html():
    server_name = ''
    server_mobile = ''
    try:
        if session.get('user_id'):
            conn = get_db()
            row = conn.execute('SELECT name, mobile FROM users WHERE id = ?', (session.get('user_id'),)).fetchone()
            if row:
                server_name = row['name'] or ''
                server_mobile = row['mobile'] or ''
    except Exception:
        pass
    server_role = 'user' if session.get('is_admin') is not True and session.get('user_id') else ''
    return render_template('about.html', server_name=server_name, server_mobile=server_mobile, server_role=server_role)


@app.route('/admin.html')
def admin_html():
    # Redirect to login if not authenticated as admin
    print('[admin_html] session at entry:', dict(session))
    if not session.get('user_id') or not session.get('is_admin'):
        return redirect(url_for('index'))
    
    server_name = ''
    server_mobile = ''
    try:
        if session.get('user_id'):
            conn = get_db()
            row = conn.execute('SELECT name, mobile FROM users WHERE id = ?', (session.get('user_id'),)).fetchone()
            if row:
                server_name = row['name'] or ''
                server_mobile = row['mobile'] or ''
    except Exception:
        pass
    server_role = 'admin' if session.get('is_admin') else ''
    return render_template('admin.html', server_name=server_name, server_mobile=server_mobile, server_role=server_role)


@app.route('/index.html')
def index_html():
    server_name = ''
    server_mobile = ''
    try:
        if session.get('user_id'):
            conn = get_db()
            row = conn.execute('SELECT name, mobile FROM users WHERE id = ?', (session.get('user_id'),)).fetchone()
            if row:
                server_name = row['name'] or ''
                server_mobile = row['mobile'] or ''
    except Exception:
        pass
    server_role = 'admin' if session.get('is_admin') else ('user' if session.get('user_id') else '')
    print('[index_html] session:', dict(session))
    return render_template('index.html', server_name=server_name, server_mobile=server_mobile, server_role=server_role)


@app.route('/login.html')
def login_html():
    # Prevent showing login UI to already-authenticated users
    if session.get('user_id'):
        if session.get('is_admin'):
            return redirect(url_for('admin_html'))
        else:
            return redirect(url_for('about_html'))
    return render_template('login.html')


@app.route('/orders.html')
def orders_html():
    server_name = ''
    server_mobile = ''
    try:
        if session.get('user_id'):
            conn = get_db()
            row = conn.execute('SELECT name, mobile FROM users WHERE id = ?', (session.get('user_id'),)).fetchone()
            if row:
                server_name = row['name'] or ''
                server_mobile = row['mobile'] or ''
    except Exception:
        pass
    server_role = 'admin' if session.get('is_admin') else ('user' if session.get('user_id') else '')
    return render_template('orders.html', server_name=server_name, server_mobile=server_mobile, server_role=server_role)


@app.route('/ratings.html')
def ratings_html():
    return render_template('ratings.html')


@app.route('/feedback.html')
def feedback_html():
    return render_template('feedback.html')


def _json_load(s):
    import json
    try:
        return json.loads(s)
    except Exception:
        return {}

# Razorpay configuration (test keys provided)
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_RzovAOzMUtkoy4')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '8cxFDh7EJeTRNZtrZ4KgPFCL')

import requests, time

print('[razorpay] using key id:', RAZORPAY_KEY_ID)


@app.route('/api/orders', methods=['GET'])
def api_get_orders():
    conn = get_db()
    mobile = request.args.get('mobile')
    if mobile:
        rows = conn.execute('SELECT * FROM orders WHERE mobile = ? ORDER BY created_at DESC', (mobile,)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    orders = []
    for r in rows:
        orders.append({
            'id': r['id'],
            'name': r['name'],
            'mobile': r['mobile'],
            'payment': r['payment'],
            'preOrder': bool(r['pre_order']),
            'delivery': None if not r['delivery_date'] else {'date': r['delivery_date'], 'time': r['delivery_time']},
            'items': _json_load(r['items']),
            'status': r['status'],
            'created_at': r['created_at']
        })
    return jsonify(orders)


@app.route('/api/orders', methods=['POST'])
def api_create_order():
    import json
    data = request.get_json() or {}
    if not data.get('id'):
        return jsonify({'error': 'missing id'}), 400
    # If user is logged-in server-side, trust server-side name/mobile
    try:
        if session.get('user_id'):
            conn = get_db()
            u = conn.execute('SELECT name, mobile FROM users WHERE id = ?', (session.get('user_id'),)).fetchone()
            if u:
                data['name'] = u['name']
                data['mobile'] = u['mobile']
    except Exception:
        pass
    # Normalize mobile if provided by client
    if data.get('mobile'):
        try:
            data['mobile'] = normalize_mobile(data.get('mobile'))
        except Exception:
            pass
    conn = get_db()
    # If this is a pre-order, ensure delivery date is at least one day in future
    try:
        if data.get('preOrder') and data.get('delivery') and data.get('delivery').get('date'):
            try:
                delivery_date = datetime.datetime.fromisoformat(data.get('delivery').get('date'))
            except Exception:
                # Try parsing as date only
                delivery_date = datetime.datetime.strptime(data.get('delivery').get('date'), '%Y-%m-%d')
            now = datetime.datetime.now()
            delta = delivery_date - now
            if delta < datetime.timedelta(days=1):
                return jsonify({'error': 'Pre-orders must be placed at least one day before delivery'}), 400
    except Exception:
        pass
    try:
        with conn:
            conn.execute(
                'INSERT INTO orders (id, name, mobile, payment, pre_order, delivery_date, delivery_time, items, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    data.get('id'),
                    data.get('name'),
                    data.get('mobile'),
                    data.get('payment'),
                    1 if data.get('preOrder') else 0,
                    data.get('delivery', {}).get('date') if data.get('delivery') else None,
                    data.get('delivery', {}).get('time') if data.get('delivery') else None,
                    json.dumps(data.get('items') or {}),
                    data.get('status') or 'PENDING'
                )
            )
    except sqlite3.IntegrityError:
        return jsonify({'error': 'order exists'}), 409
    return jsonify({'ok': True})


@app.route('/api/orders/<order_id>/status', methods=['PUT'])
def api_update_status(order_id):
    data = request.get_json() or {}
    status = data.get('status')
    if not status:
        return jsonify({'error': 'missing status'}), 400
    conn = get_db()
    with conn:
        conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    # Create a notification for the user about status change
    try:
        row = conn.execute('SELECT mobile, pre_order, delivery_date, delivery_time FROM orders WHERE id = ?', (order_id,)).fetchone()
        if row and row['mobile']:
            user_mobile = row['mobile']
            msg = ''
            eta = None
            if status == 'ACCEPTED':
                if row['pre_order']:
                    # Pre-order accepted: inform scheduled delivery
                    dd = row['delivery_date'] or ''
                    dt = row['delivery_time'] or ''
                    msg = f'Your pre-order {order_id} has been accepted. Scheduled delivery: {dd} {dt}'.strip()
                else:
                    # Normal order accepted: give ETA (minutes)
                    eta = 30
                    msg = f'Your order {order_id} has been accepted. Estimated delivery in {eta} minutes.'
            elif status == 'DECLINED':
                msg = f'Your order {order_id} was declined. Please contact support.'
            else:
                msg = f'Order {order_id} status updated to {status}.'
            if msg:
                with conn:
                    conn.execute('INSERT INTO notifications (user_mobile, message, order_id, eta_minutes) VALUES (?, ?, ?, ?)', (user_mobile, msg, order_id, eta))
    except Exception:
        pass
    return jsonify({'ok': True})


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out')
    return redirect(url_for('index'))



### Ratings API ###
@app.route('/api/ratings', methods=['GET'])
def api_get_ratings():
    conn = get_db()
    rows = conn.execute('SELECT * FROM ratings ORDER BY created_at DESC').fetchall()
    ratings = []
    for r in rows:
        ratings.append({
            'id': r['id'],
            'user_name': r['user_name'],
            'user_mobile': r['user_mobile'],
            'item_name': r['item_name'],
            'rating': r['rating'],
            'review': r['review'],
            'created_at': r['created_at']
        })
    return jsonify(ratings)


@app.route('/api/ratings', methods=['POST'])
def api_create_rating():
    import json
    data = request.get_json() or {}
    user_mobile = data.get('user_mobile')
    user_name = data.get('user_name')
    item_name = data.get('item_name')
    rating = data.get('rating')
    review = data.get('review', '')
    
    if not all([user_mobile, item_name, rating]):
        return jsonify({'error': 'missing fields'}), 400
    
    if not (1 <= int(rating) <= 5):
        return jsonify({'error': 'rating must be 1-5'}), 400
    
    conn = get_db()
    try:
        with conn:
            conn.execute(
                'INSERT INTO ratings (user_mobile, user_name, item_name, rating, review) VALUES (?, ?, ?, ?, ?)',
                (user_mobile, user_name, item_name, rating, review)
            )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True})


@app.route('/api/ratings/item/<item_name>', methods=['GET'])
def api_get_item_ratings(item_name):
    conn = get_db()
    rows = conn.execute('SELECT * FROM ratings WHERE item_name = ? ORDER BY created_at DESC', (item_name,)).fetchall()
    ratings = [{'rating': r['rating'], 'review': r['review'], 'user_name': r['user_name'], 'created_at': r['created_at']} for r in rows]
    avg_rating = 0
    if ratings:
        avg_rating = sum(r['rating'] for r in ratings) / len(ratings)
    return jsonify({'item': item_name, 'avg_rating': round(avg_rating, 1), 'count': len(ratings), 'ratings': ratings})


@app.route('/api/favorites', methods=['GET'])
def api_get_favorites():
    mobile = request.args.get('mobile')
    if not mobile:
        return jsonify({'error': 'missing mobile'}), 400
    conn = get_db()
    rows = conn.execute('SELECT item_name FROM favorites WHERE user_mobile = ? ORDER BY created_at DESC', (mobile,)).fetchall()
    items = [r['item_name'] for r in rows]
    return jsonify({'ok': True, 'favorites': items})


@app.route('/api/favorites', methods=['POST'])
def api_add_favorite():
    data = request.get_json() or {}
    mobile = data.get('mobile')
    item = data.get('item')
    if not mobile or not item:
        return jsonify({'error': 'missing fields'}), 400
    conn = get_db()
    try:
        with conn:
            conn.execute('INSERT OR IGNORE INTO favorites (user_mobile, item_name) VALUES (?, ?)', (mobile, item))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True})


@app.route('/api/favorites', methods=['DELETE'])
def api_remove_favorite():
    # Accept JSON body or query parameters to support clients that drop DELETE bodies
    data = request.get_json(silent=True) or {}
    mobile = data.get('mobile') or request.args.get('mobile')
    item = data.get('item') or request.args.get('item')
    if not mobile or not item:
        return jsonify({'error': 'missing fields'}), 400
    conn = get_db()
    with conn:
        conn.execute('DELETE FROM favorites WHERE user_mobile = ? AND item_name = ?', (mobile, item))
    return jsonify({'ok': True})


@app.route('/api/notifications', methods=['GET'])
def api_get_notifications():
    mobile = request.args.get('mobile')
    if not mobile:
        return jsonify({'error': 'missing mobile'}), 400
    mobile = normalize_mobile(mobile)
    conn = get_db()
    rows = conn.execute('SELECT * FROM notifications WHERE user_mobile = ? ORDER BY created_at DESC', (mobile,)).fetchall()
    notes = []
    for r in rows:
        notes.append({
            'id': r['id'], 'message': r['message'], 'order_id': r['order_id'], 'eta_minutes': r['eta_minutes'], 'created_at': r['created_at'], 'read': bool(r['read'])
        })
    return jsonify({'ok': True, 'notifications': notes})


@app.route('/api/notifications', methods=['POST'])
def api_create_notification():
    data = request.get_json() or {}
    mobile = data.get('mobile')
    message = data.get('message')
    order_id = data.get('order_id')
    eta = data.get('eta_minutes')
    if not mobile or not message:
        return jsonify({'error': 'missing fields'}), 400
    mobile = normalize_mobile(mobile)
    conn = get_db()
    with conn:
        conn.execute('INSERT INTO notifications (user_mobile, message, order_id, eta_minutes) VALUES (?, ?, ?, ?)', (mobile, message, order_id, eta))
    return jsonify({'ok': True})


@app.route('/api/razorpay_order', methods=['POST'])
def api_razorpay_order():
    data = request.get_json() or {}
    try:
        amount = int(float(data.get('amount') or 0))  # rupees
    except Exception:
        amount = 0
    if amount <= 0:
        return jsonify({'error': 'invalid amount'}), 400
    payload = {
        'amount': amount * 100,
        'currency': 'INR',
        'receipt': data.get('receipt') or f'receipt_{int(time.time())}',
        'payment_capture': 1
    }
    try:
        resp = requests.post('https://api.razorpay.com/v1/orders', auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET), json=payload, timeout=10)
        print('[razorpay] status', resp.status_code)
        if resp.status_code not in (200, 201):
            print('[razorpay] error response:', resp.text)
            return jsonify({'error': 'razorpay error', 'detail': resp.text}), 500
        order_data = resp.json()
        print('[razorpay] order created id=', order_data.get('id'))
        return jsonify({'ok': True, 'order': order_data, 'key_id': RAZORPAY_KEY_ID})
    except Exception as e:
        print('[razorpay] exception', str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/api/recommendations', methods=['GET'])
def api_recommendations():
    """Return recommended item names for a user based on past orders (most frequently ordered items).
    Response: { recommendations: [itemName, ...] }
    """
    mobile = request.args.get('mobile')
    conn = get_db()
    rows = []
    if mobile:
        rows = conn.execute('SELECT items FROM orders WHERE mobile = ?', (mobile,)).fetchall()
    else:
        rows = conn.execute('SELECT items FROM orders').fetchall()
    # aggregate counts from JSON stored in items column
    import json
    counts = {}
    for r in rows:
        try:
            items = json.loads(r['items'] or '{}')
            if isinstance(items, dict):
                for name, qty in items.items():
                    try:
                        qtyn = int(qty)
                    except Exception:
                        qtyn = 1
                    counts[name] = counts.get(name, 0) + qtyn
        except Exception:
            continue
    # sort by count desc
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    recommendations = [name for name, _ in sorted_items][:8]
    return jsonify({'ok': True, 'recommendations': recommendations})


@app.route('/api/orders/<order_id>/cancel', methods=['POST'])
def api_cancel_order(order_id):
    conn = get_db()
    with conn:
        conn.execute('UPDATE orders SET status = ? WHERE id = ?', ('CANCELLED', order_id))
    return jsonify({'ok': True})


@app.route('/api/orders/<order_id>', methods=['DELETE'])
def api_delete_order(order_id):
    conn = get_db()
    with conn:
        conn.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
