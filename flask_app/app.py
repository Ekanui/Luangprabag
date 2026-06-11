from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3, os, datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'heritage-lp-secret-2026')

DB_PATH = os.environ.get('DB_PATH', 'heritage.db')
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ── DB helpers ─────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript(open('schema.sql').read())

# ── File upload helper ─────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ── Public routes ──────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/heritage')
def heritage_detail():
    qr_id = request.args.get('id', '')
    lang  = request.args.get('lang', 'lo')
    return render_template('heritage_detail.html', qr_id=qr_id, lang=lang)

# ── API: get heritage by QR code ───────────────────────────────
@app.route('/api/get_heritage', methods=['POST'])
def api_get_heritage():
    qr_code = request.form.get('qr_code', '').strip()
    lang    = request.form.get('lang', 'lo')

    if not qr_code:
        return jsonify({'success': False, 'message': 'QR code is required'})

    # Strip full URL down to just the ID if needed
    if 'heritage' in qr_code and 'id=' in qr_code:
        qr_code = qr_code.split('id=')[-1].split('&')[0]

    try:
        with get_db() as conn:
            house = conn.execute(
                "SELECT * FROM heritage_houses WHERE qr_code = ? AND status = 'active'",
                (qr_code,)
            ).fetchone()

            if not house:
                msg = 'ບໍ່ພົບຂໍ້ມູນ QR Code ນີ້' if lang == 'lo' else 'Heritage house not found'
                return jsonify({'success': False, 'message': msg})

            images = conn.execute(
                "SELECT * FROM heritage_images WHERE house_id = ? ORDER BY display_order",
                (house['house_id'],)
            ).fetchall()

            house_dict = dict(house)
            house_dict['images'] = [dict(img) for img in images]

        return jsonify({'success': True, 'data': house_dict})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ── API: log visit ─────────────────────────────────────────────
@app.route('/api/log_visit', methods=['POST'])
def api_log_visit():
    house_id = request.form.get('house_id')
    # Session-based deduplication — only log once per house per session
    session_key = f'visited_{house_id}'
    if session.get(session_key):
        return jsonify({'success': True, 'skipped': True})
    try:
        visitor_ip  = request.remote_addr
        user_agent  = request.user_agent.string[:255]
        today       = datetime.date.today().isoformat()
        now         = datetime.datetime.now().strftime('%H:%M:%S')
        with get_db() as conn:
            conn.execute(
                "INSERT INTO visit_logs (house_id, visitor_ip, visitor_device, visit_date, visit_time) VALUES (?,?,?,?,?)",
                (house_id, visitor_ip, user_agent, today, now)
            )
        session[session_key] = True
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ── API: search heritage ───────────────────────────────────────
@app.route('/api/search_heritage', methods=['POST'])
def api_search_heritage():
    keyword = request.form.get('keyword', '').strip()
    lang    = request.form.get('lang', 'lo')
    if not keyword:
        return jsonify([])
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT house_id, qr_code, house_number,
                       house_name_lo, house_name_en,
                       architectural_style_lo, architectural_style_en
                FROM heritage_houses
                WHERE status = 'active'
                  AND (house_name_lo LIKE ? OR house_name_en LIKE ? OR house_number LIKE ?)
                LIMIT 20
            """, (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify([])

# ── Admin: login / logout ──────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ? AND status = 'active'",
                (username,)
            ).fetchone()
        if user and check_password_hash(user['password'], password):
            session['admin_id']   = user['user_id']
            session['admin_name'] = user['username']
            session['admin_role'] = user['role']
            with get_db() as conn:
                conn.execute(
                    "UPDATE users SET last_login = ? WHERE user_id = ?",
                    (datetime.datetime.now().isoformat(), user['user_id'])
                )
            return redirect(url_for('admin_dashboard'))
        flash('ຊື່ຜູ້ໃຊ້ ຫຼື ລະຫັດຜ່ານບໍ່ຖືກຕ້ອງ | Invalid username or password', 'danger')
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ── Admin: dashboard ──────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    with get_db() as conn:
        total_houses = conn.execute("SELECT COUNT(*) FROM heritage_houses WHERE status='active'").fetchone()[0]
        total_visits = conn.execute("SELECT COUNT(*) FROM visit_logs").fetchone()[0]
        today_visits = conn.execute(
            "SELECT COUNT(*) FROM visit_logs WHERE visit_date = ?",
            (datetime.date.today().isoformat(),)
        ).fetchone()[0]
        recent = conn.execute(
            "SELECT h.house_name_lo, h.house_name_en, COUNT(v.log_id) as visits "
            "FROM heritage_houses h LEFT JOIN visit_logs v ON h.house_id = v.house_id "
            "WHERE h.status = 'active' GROUP BY h.house_id ORDER BY visits DESC LIMIT 5"
        ).fetchall()
    return render_template('admin/dashboard.html',
        total_houses=total_houses,
        total_visits=total_visits,
        today_visits=today_visits,
        recent=recent
    )

# ── Admin: list houses ─────────────────────────────────────────
@app.route('/admin/houses')
@admin_required
def admin_houses():
    with get_db() as conn:
        houses = conn.execute(
            "SELECT * FROM heritage_houses ORDER BY created_at DESC"
        ).fetchall()
    return render_template('admin/houses.html', houses=houses)

# ── Admin: add house ───────────────────────────────────────────
@app.route('/admin/houses/add', methods=['GET', 'POST'])
@admin_required
def admin_add_house():
    if request.method == 'POST':
        f = request.form
        image_main = None
        if 'image_main' in request.files:
            file = request.files['image_main']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{int(datetime.datetime.now().timestamp())}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_main = filename
        try:
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO heritage_houses
                    (qr_code, house_number, house_name_lo, house_name_en,
                     owner_name_lo, owner_name_en, construction_year,
                     architectural_style_lo, architectural_style_en,
                     historical_significance_lo, historical_significance_en,
                     description_lo, description_en,
                     image_main, status, house_type, building_material,
                     latitude, longitude)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    f['qr_code'], f.get('house_number'), f.get('house_name_lo'), f.get('house_name_en'),
                    f.get('owner_name_lo'), f.get('owner_name_en'), f.get('construction_year') or None,
                    f.get('architectural_style_lo'), f.get('architectural_style_en'),
                    f.get('historical_significance_lo'), f.get('historical_significance_en'),
                    f.get('description_lo'), f.get('description_en'),
                    image_main, f.get('status', 'active'), f.get('house_type'), f.get('building_material'),
                    f.get('latitude') or None, f.get('longitude') or None
                ))
            flash('ເພີ່ມຂໍ້ມູນສຳເລັດ | House added successfully', 'success')
            return redirect(url_for('admin_houses'))
        except sqlite3.IntegrityError:
            flash('QR Code ນີ້ມີຢູ່ແລ້ວ | QR Code already exists', 'danger')
    return render_template('admin/add_house.html')

# ── Admin: edit house ──────────────────────────────────────────
@app.route('/admin/houses/edit/<int:house_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_house(house_id):
    with get_db() as conn:
        house = conn.execute("SELECT * FROM heritage_houses WHERE house_id = ?", (house_id,)).fetchone()
    if not house:
        flash('ບໍ່ພົບຂໍ້ມູນ', 'danger')
        return redirect(url_for('admin_houses'))
    if request.method == 'POST':
        f = request.form
        image_main = house['image_main']
        if 'image_main' in request.files:
            file = request.files['image_main']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{int(datetime.datetime.now().timestamp())}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_main = filename
        with get_db() as conn:
            conn.execute("""
                UPDATE heritage_houses SET
                qr_code=?, house_number=?, house_name_lo=?, house_name_en=?,
                owner_name_lo=?, owner_name_en=?, construction_year=?,
                architectural_style_lo=?, architectural_style_en=?,
                historical_significance_lo=?, historical_significance_en=?,
                description_lo=?, description_en=?,
                image_main=?, status=?, house_type=?, building_material=?,
                latitude=?, longitude=?, updated_at=?
                WHERE house_id=?
            """, (
                f['qr_code'], f.get('house_number'), f.get('house_name_lo'), f.get('house_name_en'),
                f.get('owner_name_lo'), f.get('owner_name_en'), f.get('construction_year') or None,
                f.get('architectural_style_lo'), f.get('architectural_style_en'),
                f.get('historical_significance_lo'), f.get('historical_significance_en'),
                f.get('description_lo'), f.get('description_en'),
                image_main, f.get('status', 'active'), f.get('house_type'), f.get('building_material'),
                f.get('latitude') or None, f.get('longitude') or None,
                datetime.datetime.now().isoformat(), house_id
            ))
        flash('ອັບເດດສຳເລັດ | Updated successfully', 'success')
        return redirect(url_for('admin_houses'))
    return render_template('admin/edit_house.html', house=house)

# ── Admin: delete house ────────────────────────────────────────
@app.route('/admin/houses/delete/<int:house_id>', methods=['POST'])
@admin_required
def admin_delete_house(house_id):
    with get_db() as conn:
        conn.execute("DELETE FROM heritage_houses WHERE house_id = ?", (house_id,))
    return jsonify({'success': True})

# ── Admin: add image to house ──────────────────────────────────
@app.route('/admin/houses/<int:house_id>/images', methods=['POST'])
@admin_required
def admin_add_image(house_id):
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'No file'})
    file = request.files['image']
    if not file or not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Invalid file'})
    filename = secure_filename(f"{int(datetime.datetime.now().timestamp())}_{file.filename}")
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    caption_lo = request.form.get('caption_lo', '')
    caption_en = request.form.get('caption_en', '')
    order      = request.form.get('display_order', 0)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO heritage_images (house_id, image_path, image_caption_lo, image_caption_en, display_order) VALUES (?,?,?,?,?)",
            (house_id, filename, caption_lo, caption_en, order)
        )
    return jsonify({'success': True, 'filename': filename})

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(debug=True, port=5000)
