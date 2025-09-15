import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify, send_file
from functools import wraps
import secrets
import math
import io
import csv

app = Flask(__name__)
# For production, always use a strong secret key from environment variables.
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))

# --- Application Configuration ---
CLASS_NAME = 'B.Sc. - Anthro'
BATCH_CODE = 'BSC'
GEOFENCE_RADIUS = 50  # Radius in meters

# --- Controller Credentials (best practice: use environment variables) ---
CONTROLLER_USERNAME = os.environ.get('BSC_CONTROLLER_USER', 'bsc_controller')
CONTROLLER_PASSWORD = os.environ.get('BSC_CONTROLLER_PASS', 'bsc_pass_123')
CONTROLLER_DISPLAY_NAME = "B.Sc. Anthro Dept Controller"

# --- Database Connection ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("FATAL: The DATABASE_URL environment variable is not set.")

def get_db_connection():
    """Establishes a reliable connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("SET TIME ZONE 'UTC';")
        conn.commit()
        return conn
    except psycopg2.OperationalError as e:
        print(f"FATAL: Database connection failed: {e}")
        return None

# --- Decorator for B.Sc. Controller ---
def controller_required(f):
    """Decorator to protect routes that require B.Sc. controller login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'bsc_controller': # Check for bsc_controller role
            if request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "message": "Unauthorized: Please log in as controller.",
                    "category": "error"
                }), 401
            else:
                flash("You must be logged in as the B.Sc. controller to access this page.", "warning")
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Helper Functions (No changes needed) ---
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_class_id_by_name(cursor):
    cursor.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_controller_id_by_username(cursor):
    # Note: The app uses the CONTROLLER_USERNAME variable, not a hardcoded string
    cursor.execute("SELECT id FROM users WHERE username = %s", (CONTROLLER_USERNAME,))
    result = cursor.fetchone()
    return result[0] if result else None

# --- Main Routes ---
@app.route('/')
def home():
    if 'user_id' in session and session.get('role') == 'bsc_controller': # Check for bsc_controller role
        return redirect(url_for('controller_dashboard'))
    return redirect(url_for('student_page'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        conn = get_db_connection()
        if not conn:
            flash("Database service unavailable.", "danger")
            return render_template('login.html', class_name=CLASS_NAME)
        try:
            with conn.cursor() as cur:
                if username == CONTROLLER_USERNAME and password == CONTROLLER_PASSWORD:
                    controller_id = get_controller_id_by_username(cur)
                    if controller_id:
                        session.clear()
                        session['user_id'] = controller_id
                        session['username'] = username
                        session['role'] = 'bsc_controller' # Set bsc_controller role
                        return redirect(url_for('controller_dashboard'))
                    else:
                        flash("Controller user not configured correctly in the database.", "danger")
                else:
                    flash("Invalid username or password.", "danger")
        finally:
            if conn: conn.close()
    return render_template('login.html', class_name=CLASS_NAME)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('login'))

@app.route('/student')
def student_page():
    active_session = None
    present_students = None
    conn = get_db_connection()
    todays_date = datetime.now(timezone.utc).strftime('%A, %B %d, %Y')

    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                class_id = get_class_id_by_name(cur)
                if class_id:
                    cur.execute("SELECT id, end_time FROM attendance_sessions WHERE class_id = %s AND is_active = TRUE AND end_time > NOW() LIMIT 1", (class_id,))
                    session_data = cur.fetchone()
                    if session_data:
                        active_session = {'id': session_data['id'], 'end_time': session_data['end_time'].isoformat()}
                    else:
                        today_utc = datetime.now(timezone.utc).date()
                        cur.execute("""
                            SELECT s.name, s.enrollment_no FROM attendance_records ar
                            JOIN students s ON ar.student_id = s.id
                            JOIN attendance_sessions ases ON ar.session_id = ases.id
                            WHERE ases.class_id = %s AND DATE(ases.start_time AT TIME ZONE 'UTC') = %s
                            ORDER BY s.enrollment_no ASC
                        """, (class_id, today_utc))
                        present_students = cur.fetchall()
        finally:
            if conn: conn.close()

    return render_template('student_attendance.html', active_session=active_session, present_students=present_students, class_name=CLASS_NAME, todays_date=todays_date)

@app.route('/controller_dashboard')
@controller_required
def controller_dashboard():
    active_session = None
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                class_id = get_class_id_by_name(cur)
                if class_id:
                    cur.execute("SELECT id, end_time FROM attendance_sessions WHERE class_id = %s AND is_active = TRUE AND end_time > NOW() LIMIT 1", (class_id,))
                    session_data = cur.fetchone()
                    if session_data:
                        active_session = {'id': session_data['id'], 'end_time': session_data['end_time'].isoformat()}
        finally:
            if conn: conn.close()
    return render_template('admin_dashboard.html', active_session=active_session, class_name=CLASS_NAME, username=session.get('username'))

# The rest of the file (reports, editing, APIs) remains the same as the logic is driven by the
# CLASS_NAME and BATCH_CODE variables. It can be copied directly from your original app.py.
# For completeness, the full code is provided below.

@app.route('/attendance_report')
@controller_required
def attendance_report():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for('controller_dashboard'))
    
    report_data, students = [], []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            class_id = get_class_id_by_name(cur)
            cur.execute("SELECT id, name, enrollment_no FROM students WHERE batch = %s ORDER BY enrollment_no", (BATCH_CODE,))
            students = cur.fetchall()
            
            cur.execute("SELECT DISTINCT DATE(start_time AT TIME ZONE 'UTC') as class_date FROM attendance_sessions WHERE class_id = %s ORDER BY class_date DESC", (class_id,))
            class_dates = [row['class_date'] for row in cur.fetchall()]

            today_utc = datetime.now(timezone.utc).date()

            for class_date in class_dates:
                is_editable = (today_utc - class_date).days < 7
                daily_entry = {'date': class_date.strftime('%Y-%m-%d'), 'students': [], 'is_editable': is_editable}
                
                cur.execute("SELECT DISTINCT student_id FROM attendance_records ar JOIN attendance_sessions s ON ar.session_id = s.id WHERE s.class_id = %s AND DATE(s.start_time AT TIME ZONE 'UTC') = %s", (class_id, class_date))
                present_ids = {row['student_id'] for row in cur.fetchall()}
                
                student_statuses = []
                for student in students:
                    status = 'Present' if student['id'] in present_ids else 'Absent'
                    student_statuses.append({'status': status})
                daily_entry['students'] = student_statuses
                report_data.append(daily_entry)
    finally:
        if conn: conn.close()

    return render_template('attendance_report.html', report_data=report_data, students=students, class_name=CLASS_NAME)

@app.route('/export_csv')
@controller_required
def export_csv():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for('attendance_report'))
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            class_id = get_class_id_by_name(cur)
            if not class_id:
                flash("Class not found for export.", "danger")
                return redirect(url_for('attendance_report'))

            cur.execute("SELECT id, enrollment_no, name FROM students WHERE batch = %s ORDER BY enrollment_no ASC", (BATCH_CODE,))
            students = cur.fetchall()
            
            cur.execute("SELECT DISTINCT DATE(start_time AT TIME ZONE 'UTC') AS session_date FROM attendance_sessions WHERE class_id = %s ORDER BY session_date ASC", (class_id,))
            session_dates = [row['session_date'] for row in cur.fetchall()]
            
            if not session_dates:
                flash("No attendance data to export.", "info")
                return redirect(url_for('attendance_report'))

            cur.execute("""
                SELECT ar.student_id, DATE(s.start_time AT TIME ZONE 'UTC') AS session_date
                FROM attendance_records ar JOIN attendance_sessions s ON ar.session_id = s.id
                WHERE s.class_id = %s
            """, (class_id,))
            
            attendance_map = {}
            for rec in cur.fetchall():
                attendance_map[(rec['student_id'], rec['session_date'])] = 'Present'

            output = io.StringIO()
            writer = csv.writer(output)
            header = ['Enrollment No', 'Student Name'] + [d.strftime('%Y-%m-%d') for d in session_dates]
            writer.writerow(header)

            for student in students:
                row = [student['enrollment_no'], student['name']] + [attendance_map.get((student['id'], date), 'Absent') for date in session_dates]
                writer.writerow(row)
            
            output.seek(0)
            return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=f'BSc_Anthro_Report.csv')
    finally:
        if conn: conn.close()

@app.route('/edit_attendance_days')
@controller_required
def edit_attendance_days():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for('controller_dashboard'))
    
    session_days = []
    try:
        with conn.cursor() as cur:
            class_id = get_class_id_by_name(cur)
            cur.execute("""
                SELECT DISTINCT DATE(start_time AT TIME ZONE 'UTC') as class_date
                FROM attendance_sessions
                WHERE class_id = %s AND start_time > NOW() - INTERVAL '7 days'
                ORDER BY class_date DESC
            """, (class_id,))
            session_days = [row[0] for row in cur.fetchall()]
    except Exception as e:
        print(f"Error fetching session days: {e}")
        flash("An error occurred fetching recent class days.", "danger")
    finally:
        if conn: conn.close()
    
    return render_template('edit_attendance_day_select.html', session_days=session_days, class_name=CLASS_NAME)

@app.route('/edit_attendance_for_day/<date_str>')
@controller_required
def edit_attendance_for_day(date_str):
    try:
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        return render_template('edit_attendance_for_day.html', attendance_date=attendance_date.strftime('%Y-%m-%d'), class_name=CLASS_NAME)
    except ValueError:
        flash("Invalid date format provided.", "danger")
        return redirect(url_for('edit_attendance_days'))

# --- API Endpoints ---
@app.route('/api/mark_attendance', methods=['POST'])
def api_mark_attendance():
    data = request.form
    # Added fingerprint to required fields
    required_fields = ['enrollment_no', 'session_id', 'latitude', 'longitude', 'accuracy', 'fingerprint']
    if not all(field in data for field in required_fields):
        return jsonify({"success": False, "message": "Missing data from client.", "category": "error"}), 400

    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database service unavailable."}), 503

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            enrollment_no_upper = data['enrollment_no'].strip().upper()
            cur.execute("SELECT id FROM students WHERE enrollment_no = %s AND batch = %s", (enrollment_no_upper, BATCH_CODE))
            student = cur.fetchone()
            if not student: return jsonify({"success": False, "message": "Enrollment number not found.", "category": "danger"}), 404
            student_id = student['id']

            cur.execute("SELECT id, session_lat, session_lon FROM attendance_sessions WHERE id = %s AND is_active = TRUE AND end_time > NOW()", (data['session_id'],))
            session_info = cur.fetchone()
            if not session_info: return jsonify({"success": False, "message": "Attendance session has expired.", "category": "danger"}), 400

            # Check fingerprint first
            cur.execute("SELECT student_id FROM session_device_fingerprints WHERE session_id = %s AND fingerprint = %s", (session_info['id'], data['fingerprint']))
            fingerprint_record = cur.fetchone()
            if fingerprint_record and fingerprint_record['student_id'] != student_id:
                return jsonify({"success": False, "message": "This device has already been used by another student.", "category": "danger"}), 403

            distance = haversine_distance(float(data['latitude']), float(data['longitude']), session_info['session_lat'], session_info['session_lon'])
            if distance > GEOFENCE_RADIUS: return jsonify({"success": False, "message": f"You are {distance:.0f}m away. Please move within the {GEOFENCE_RADIUS}m radius.", "category": "danger"}), 403

            # Insert fingerprint
            cur.execute("INSERT INTO session_device_fingerprints (session_id, student_id, fingerprint) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (session_info['id'], student_id, data['fingerprint']))
            
            # Insert attendance record
            cur.execute("""
                INSERT INTO attendance_records (session_id, student_id, timestamp, latitude, longitude, ip_address) 
                VALUES (%s, %s, NOW(), %s, %s, %s) ON CONFLICT (session_id, student_id) DO NOTHING
            """, (session_info['id'], student_id, float(data['latitude']), float(data['longitude']), user_ip))
            
            if cur.rowcount == 0:
                conn.commit()
                return jsonify({"success": False, "message": "You have already marked attendance for this session.", "category": "warning"}), 409
            
            conn.commit()
            return jsonify({"success": True, "message": "Attendance marked successfully!", "category": "success"})
    except (Exception, psycopg2.Error) as e:
        if conn: conn.rollback()
        print(f"ERROR in api_mark_attendance: {e}")
        return jsonify({"success": False, "message": "A server error occurred."}), 500
    finally:
        if conn: conn.close()

@app.route('/api/start_session', methods=['POST'])
@controller_required
def api_start_session():
    data = request.get_json()
    if not data or 'latitude' not in data or 'longitude' not in data:
        return jsonify({"success": False, "message": "Location data not provided."}), 400
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database connection failed."}), 503
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            class_id = get_class_id_by_name(cur)
            if not class_id: return jsonify({"success": False, "message": f"Class '{CLASS_NAME}' not found."}), 500
            
            cur.execute("SELECT id FROM attendance_sessions WHERE class_id = %s AND is_active = TRUE AND end_time > NOW() LIMIT 1", (class_id,))
            if cur.fetchone():
                return jsonify({"success": False, "message": "An active session already exists."}), 409

            session_token = secrets.token_hex(16)
            cur.execute(
                """
                INSERT INTO attendance_sessions 
                (class_id, controller_id, session_token, start_time, end_time, is_active, session_lat, session_lon) 
                VALUES (%s, %s, %s, NOW(), NOW() + interval '5 minutes', TRUE, %s, %s) 
                RETURNING id, end_time
                """,
                (class_id, session['user_id'], session_token, data['latitude'], data['longitude'])
            )
            new_session = cur.fetchone()
            conn.commit()
            return jsonify({
                "success": True, 
                "message": "New 5-minute session started!", 
                "category": "success",
                "session": {'id': new_session['id'], 'end_time': new_session['end_time'].isoformat()}
            })
    finally:
        if conn: conn.close()

@app.route('/api/end_session/<int:session_id>', methods=['POST'])
@controller_required
def api_end_session(session_id):
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database connection failed."})
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE attendance_sessions SET is_active = FALSE, end_time = NOW() WHERE id = %s AND controller_id = %s", (session_id, session['user_id']))
            conn.commit()
            return jsonify({"success": True, "message": "Session ended."})
    finally:
        if conn: conn.close()
        
@app.route('/api/get_student_name/<enrollment_no>')
def api_get_student_name(enrollment_no):
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "name": "DB Error"})
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM students WHERE enrollment_no = %s AND batch = %s", (enrollment_no.upper(), BATCH_CODE))
            result = cur.fetchone()
            if result: return jsonify({"success": True, "name": result[0]})
            else: return jsonify({"success": False, "name": "Not Found"})
    finally:
        if conn: conn.close()

@app.route('/api/get_present_students/<int:session_id>')
def api_get_present_students(session_id):
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "students": []})
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT s.name, s.enrollment_no FROM attendance_records ar
                JOIN students s ON ar.student_id = s.id
                WHERE ar.session_id = %s ORDER BY s.enrollment_no ASC
            """, (session_id,))
            students = [dict(row) for row in cur.fetchall()]
            return jsonify({"success": True, "students": students})
    finally:
        if conn: conn.close()

@app.route('/api/get_students_for_edit/<date_str>')
@controller_required
def api_get_students_for_edit(date_str):
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database failed."}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            class_id = get_class_id_by_name(cur)
            day_to_query = datetime.strptime(date_str, '%Y-%m-%d').date()
            cur.execute("SELECT id, enrollment_no, name FROM students WHERE batch = %s ORDER BY enrollment_no", (BATCH_CODE,))
            all_students = cur.fetchall()
            cur.execute("""
                SELECT DISTINCT ar.student_id FROM attendance_records ar
                JOIN attendance_sessions s ON ar.session_id = s.id
                WHERE s.class_id = %s AND DATE(s.start_time AT TIME ZONE 'UTC') = %s
            """, (class_id, day_to_query))
            present_ids = {row['student_id'] for row in cur.fetchall()}
            student_data = [{'id': s['id'], 'enrollment_no': s['enrollment_no'], 'name': s['name'], 'is_present': s['id'] in present_ids} for s in all_students]
            return jsonify({"success": True, "students": student_data})
    finally:
        if conn: conn.close()

@app.route('/api/update_daily_attendance', methods=['POST'])
@controller_required
def api_update_daily_attendance():
    data = request.get_json()
    date_str, student_id, is_present = data.get('date'), data.get('student_id'), data.get('is_present')
    if not all([date_str, student_id, isinstance(is_present, bool)]):
        return jsonify({"success": False, "message": "Missing data."}), 400
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database failed."}), 500
    try:
        with conn.cursor() as cur:
            class_id = get_class_id_by_name(cur)
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            cur.execute("SELECT id FROM attendance_sessions WHERE class_id = %s AND DATE(start_time AT TIME ZONE 'UTC') = %s ORDER BY start_time ASC", (class_id, target_date))
            session_ids = [row[0] for row in cur.fetchall()]
            
            if not session_ids:
                if is_present:
                    session_token = secrets.token_hex(16)
                    start_of_day = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
                    cur.execute("INSERT INTO attendance_sessions (class_id, controller_id, session_token, start_time, end_time, is_active) VALUES (%s, %s, %s, %s, %s, FALSE) RETURNING id",
                                (class_id, session['user_id'], session_token, start_of_day, start_of_day))
                    new_session_id = cur.fetchone()[0]
                    session_ids.append(new_session_id)
                else:
                    return jsonify({"success": True, "message": "Student is already absent."})

            if is_present:
                cur.execute("INSERT INTO attendance_records (session_id, student_id, timestamp, ip_address) VALUES (%s, %s, NOW(), 'Manual Edit') ON CONFLICT (session_id, student_id) DO NOTHING", (session_ids[0], student_id))
            else:
                cur.execute("DELETE FROM attendance_records WHERE student_id = %s AND session_id = ANY(%s)", (student_id, session_ids))
            conn.commit()
            return jsonify({"success": True, "message": "Attendance updated."})
    except (Exception, psycopg2.Error) as e:
        if conn: conn.rollback()
        print(f"ERROR in api_update_daily_attendance: {e}")
        return jsonify({"success": False, "message": "An error occurred."}), 500
    finally:
        if conn: conn.close()

@app.route('/api/get_students_for_manual_edit/<int:session_id>')
@controller_required
def api_get_students_for_manual_edit(session_id):
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database failed."}), 500
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, enrollment_no, name FROM students WHERE batch = %s ORDER BY enrollment_no", (BATCH_CODE,))
            all_students = cur.fetchall()
            cur.execute("SELECT student_id FROM attendance_records WHERE session_id = %s", (session_id,))
            present_ids = {row['student_id'] for row in cur.fetchall()}
            student_data = [{'id': s['id'], 'enrollment_no': s['enrollment_no'], 'name': s['name'], 'is_present': s['id'] in present_ids} for s in all_students]
            return jsonify({"success": True, "students": student_data})
    finally:
        if conn: conn.close()

@app.route('/api/manual_mark_attendance', methods=['POST'])
@controller_required
def api_manual_mark_attendance():
    data = request.get_json()
    session_id, student_id = data.get('session_id'), data.get('student_id')
    if not all([session_id, student_id]):
        return jsonify({"success": False, "message": "Missing data."}), 400
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database failed."}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO attendance_records (session_id, student_id, timestamp, ip_address) VALUES (%s, %s, NOW(), 'Manual Override') ON CONFLICT (session_id, student_id) DO NOTHING", (session_id, student_id))
            conn.commit()
            if cur.rowcount > 0:
                return jsonify({"success": True, "message": "Student marked present."})
            else:
                return jsonify({"success": False, "message": "Student already marked present."})
    except (Exception, psycopg2.Error) as e:
        if conn: conn.rollback()
        print(f"ERROR in api_manual_mark_attendance: {e}")
        return jsonify({"success": False, "message": "An error occurred."}), 500
    finally:
        if conn: conn.close()
        
@app.route('/api/delete_attendance_for_day/<date_str>', methods=['DELETE'])
@controller_required
def api_delete_attendance_for_day(date_str):
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database connection failed."}), 503
    try:
        with conn.cursor() as cur:
            class_id = get_class_id_by_name(cur)
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            cur.execute("SELECT id FROM attendance_sessions WHERE class_id = %s AND DATE(start_time AT TIME ZONE 'UTC') = %s", (class_id, target_date))
            session_ids = [row[0] for row in cur.fetchall()]
            
            if not session_ids:
                return jsonify({"success": False, "message": "No sessions found for this day."}), 404
            
            # Delete from all related tables
            cur.execute("DELETE FROM session_device_fingerprints WHERE session_id = ANY(%s)", (session_ids,))
            cur.execute("DELETE FROM attendance_records WHERE session_id = ANY(%s)", (session_ids,))
            cur.execute("DELETE FROM attendance_sessions WHERE id = ANY(%s)", (session_ids,))
            
            conn.commit()
            return jsonify({"success": True, "message": f"All attendance data for {date_str} has been deleted."})
    except (Exception, psycopg2.Error) as e:
        if conn: conn.rollback()
        print(f"ERROR deleting attendance for day: {e}")
        return jsonify({"success": False, "message": "A server error occurred during deletion."}), 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    app.run(
        host=os.environ.get('FLASK_RUN_HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', 5001)), # Changed port to 5001 to avoid conflict
        debug=os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    )