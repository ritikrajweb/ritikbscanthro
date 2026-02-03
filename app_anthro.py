import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from functools import wraps
import secrets
import math

app = Flask(__name__)
# Security: Change this in production settings on Render
app.secret_key = os.environ.get('SECRET_KEY', 'ritik_crafted_this_securely')

# --- Configurations ---
CLASS_NAME = 'Practical 4th Sem' # Merged class name

# LOCATION: Kanad Bhawan (23°49'40"N 78°46'26"E)
# Converted to Decimal: 23.82778, 78.77389
FIXED_LAT = 23.82778
FIXED_LON = 78.77389
GEOFENCE_RADIUS = 80  # Updated to 80 meters

DATABASE_URL = os.environ.get('DATABASE_URL')
CONTROLLER_USER = os.environ.get('CONTROLLER_USER', 'anthro_admin')
CONTROLLER_PASS = os.environ.get('CONTROLLER_PASS', 'admin_123')

def get_db():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

# --- Helpers ---
def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'student_id' not in session: return redirect(url_for('student_auth'))
        return f(*args, **kwargs)
    return decorated

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

# --- Routes ---

@app.route('/')
def home():
    if session.get('role') == 'controller': return redirect(url_for('controller_dashboard'))
    if 'student_id' in session: return redirect(url_for('student_dashboard'))
    return redirect(url_for('student_auth'))

@app.route('/student/auth')
def student_auth():
    if 'student_id' in session: return redirect(url_for('student_dashboard'))
    return render_template('student_auth.html', class_name=CLASS_NAME)

@app.route('/api/student/register', methods=['POST'])
def api_register():
    data = request.json
    enrollment, password, device_id = data.get('enrollment').strip().upper(), data.get('password'), data.get('device_id')
    
    conn = get_db()
    if not conn: return jsonify({'success': False, 'message': 'System unavailable'})
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Check against the full student list (B.Sc. or B.A.)
            cur.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment,))
            student = cur.fetchone()
            
            if not student: return jsonify({'success': False, 'message': 'Enrollment not found.'})
            if student['password']: return jsonify({'success': False, 'message': 'Already registered.'})
            
            cur.execute("SELECT id FROM students WHERE device_id = %s", (device_id,))
            if cur.fetchone(): return jsonify({'success': False, 'message': 'Device already used.'})
            
            cur.execute("UPDATE students SET password = %s, device_id = %s WHERE id = %s", (password, device_id, student['id']))
            conn.commit()
            return jsonify({'success': True})
    finally: conn.close()

@app.route('/api/student/login', methods=['POST'])
def api_login():
    data = request.json
    enrollment, password, device_id = data.get('enrollment').strip().upper(), data.get('password'), data.get('device_id')
    
    conn = get_db()
    if not conn: return jsonify({'success': False, 'message': 'System unavailable'})
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment,))
            student = cur.fetchone()
            
            if not student: return jsonify({'success': False, 'message': 'Student not found.'})
            if not student['password']: return jsonify({'success': False, 'message': 'Not registered yet.'})
            if student['password'] != password: return jsonify({'success': False, 'message': 'Wrong password.'})
            if student['device_id'] != device_id: return jsonify({'success': False, 'message': 'Please use your registered device.'})
            
            session['student_id'] = student['id']
            session['student_name'] = student['name']
            return jsonify({'success': True})
    finally: conn.close()

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    stats = {'total': 0, 'present': 0, 'percent': 0}
    active_session = None
    conn = get_db()
    
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Stats
                cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
                class_id = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM attendance_sessions WHERE class_id = %s AND is_active = FALSE", (class_id,))
                stats['total'] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM attendance_records WHERE student_id = %s", (session['student_id'],))
                stats['present'] = cur.fetchone()[0]
                
                if stats['total'] > 0: stats['percent'] = round((stats['present'] / stats['total']) * 100)
                
                # Active Session
                cur.execute("SELECT * FROM attendance_sessions WHERE class_id = %s AND is_active = TRUE", (class_id,))
                sess = cur.fetchone()
                if sess:
                    active_session = {'id': sess['id'], 'end_time': sess['end_time'].isoformat()}
                    # Check if already marked
                    cur.execute("SELECT 1 FROM attendance_records WHERE session_id = %s AND student_id = %s", (sess['id'], session['student_id']))
                    active_session['marked'] = cur.fetchone() is not None
        finally: conn.close()
    
    return render_template('student_attendance.html', class_name=CLASS_NAME, stats=stats, active_session=active_session, name=session['student_name'])

@app.route('/api/mark', methods=['POST'])
@student_required
def mark_attendance():
    data = request.json
    lat, lon, sid = data.get('lat'), data.get('lon'), data.get('session_id')
    
    conn = get_db()
    if not conn: return jsonify({'success': False})
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM attendance_sessions WHERE id = %s AND is_active = TRUE", (sid,))
            sess = cur.fetchone()
            if not sess: return jsonify({'success': False, 'message': 'Session expired.'})
            
            # Use the FIXED Kanad Bhawan coordinates for distance check
            dist = haversine(lat, lon, FIXED_LAT, FIXED_LON)
            
            if dist > GEOFENCE_RADIUS: 
                return jsonify({'success': False, 'message': f'Too far ({int(dist)}m). Must be at Kanad Bhawan.'})
            
            cur.execute("INSERT INTO attendance_records (session_id, student_id, timestamp, latitude, longitude, ip_address) VALUES (%s, %s, NOW(), %s, %s, 'Mobile') ON CONFLICT DO NOTHING",
                       (sid, session['student_id'], lat, lon))
            conn.commit()
            return jsonify({'success': True})
    finally: conn.close()

@app.route('/student/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- Controller Routes ---
@app.route('/login', methods=['GET', 'POST'])
def controller_login():
    if request.method == 'POST':
        if request.form.get('username') == CONTROLLER_USER and request.form.get('password') == CONTROLLER_PASS:
            session['role'] = 'controller'
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE username = %s", (CONTROLLER_USER,))
                session['user_id'] = cur.fetchone()[0]
            conn.close()
            return redirect(url_for('controller_dashboard'))
    return render_template('student_auth.html', class_name=CLASS_NAME, is_admin=True)

@app.route('/controller')
def controller_dashboard():
    if session.get('role') != 'controller': return redirect(url_for('controller_login'))
    
    conn = get_db()
    active_session = None
    if conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            cur.execute("SELECT id, end_time FROM attendance_sessions WHERE class_id = %s AND is_active = TRUE", (class_id,))
            sess = cur.fetchone()
            if sess: active_session = {'id': sess['id'], 'end_time': sess['end_time'].isoformat()}
        conn.close()
    return render_template('admin_dashboard.html', class_name=CLASS_NAME, active_session=active_session)

@app.route('/api/session/start', methods=['POST'])
def start_session():
    if session.get('role') != 'controller': return jsonify({'success': False})
    
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            token = secrets.token_hex(4)
            
            # Storing FIXED_LAT/LON in the session record
            cur.execute("""INSERT INTO attendance_sessions (class_id, controller_id, session_token, start_time, end_time, session_lat, session_lon) 
                        VALUES (%s, %s, %s, NOW(), NOW() + interval '5 minutes', %s, %s)""", 
                        (class_id, session['user_id'], token, FIXED_LAT, FIXED_LON))
            conn.commit()
            return jsonify({'success': True})
    finally: conn.close()

@app.route('/api/session/end', methods=['POST'])
def end_session():
    if session.get('role') != 'controller': return jsonify({'success': False})
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE attendance_sessions SET is_active = FALSE WHERE is_active = TRUE")
            conn.commit()
            return jsonify({'success': True})
    finally: conn.close()

@app.route('/report')
def report():
    if session.get('role') != 'controller': return redirect(url_for('controller_login'))
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            
            # Fetch ALL students (both BA and BSC)
            cur.execute("SELECT name, enrollment_no, id, batch FROM students ORDER BY batch, enrollment_no")
            students = cur.fetchall()
            
            cur.execute("SELECT id, start_time::date FROM attendance_sessions WHERE class_id = %s ORDER BY start_time DESC", (class_id,))
            sessions = cur.fetchall()
            
            report_data = []
            for s in students:
                row = {'name': s['name'], 'roll': s['enrollment_no'], 'batch': s['batch'], 'attendance': []}
                for sess in sessions:
                    cur.execute("SELECT 1 FROM attendance_records WHERE session_id = %s AND student_id = %s", (sess['id'], s['id']))
                    row['attendance'].append('P' if cur.fetchone() else 'A')
                report_data.append(row)
                
            dates = [s[1].strftime('%d-%b') for s in sessions]
            return render_template('attendance_report.html', dates=dates, report=report_data, class_name=CLASS_NAME)
    finally: conn.close()

if __name__ == '__main__':
    app.run(port=5000)