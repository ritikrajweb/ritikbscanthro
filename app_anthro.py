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
CLASS_NAME = 'Practical 4th Sem'
BATCH_CODE = 'BSC'
GEOFENCE_RADIUS = 80  

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
    R = 6371000 
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
                cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
                class_id = cur.fetchone()[0]
                
                cur.execute("""
                    SELECT COUNT(DISTINCT DATE(start_time AT TIME ZONE 'UTC')) 
                    FROM attendance_sessions 
                    WHERE class_id = %s AND is_active = FALSE
                """, (class_id,))
                stats['total'] = cur.fetchone()[0]
                
                cur.execute("""
                    SELECT COUNT(DISTINCT DATE(s.start_time AT TIME ZONE 'UTC')) 
                    FROM attendance_records r
                    JOIN attendance_sessions s ON r.session_id = s.id
                    WHERE r.student_id = %s AND s.class_id = %s
                """, (session['student_id'], class_id))
                stats['present'] = cur.fetchone()[0]
                
                if stats['total'] > 0: stats['percent'] = round((stats['present'] / stats['total']) * 100)
                
                cur.execute("SELECT * FROM attendance_sessions WHERE class_id = %s AND is_active = TRUE", (class_id,))
                sess = cur.fetchone()
                if sess:
                    active_session = {'id': sess['id'], 'end_time': sess['end_time'].isoformat()}
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
            
            dist = haversine(lat, lon, sess['session_lat'], sess['session_lon'])
            if dist > GEOFENCE_RADIUS: 
                return jsonify({'success': False, 'message': f'Too far ({int(dist)}m). Move closer.'})
            
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
    dashboard_stats = {'total_classes': 0, 'avg_attendance': 0}
    
    if conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            
            cur.execute("SELECT id, end_time FROM attendance_sessions WHERE class_id = %s AND is_active = TRUE", (class_id,))
            sess = cur.fetchone()
            if sess: active_session = {'id': sess['id'], 'end_time': sess['end_time'].isoformat()}
            
            cur.execute("""
                SELECT COUNT(DISTINCT DATE(start_time AT TIME ZONE 'UTC')) 
                FROM attendance_sessions 
                WHERE class_id = %s AND is_active = FALSE
            """, (class_id,))
            dashboard_stats['total_classes'] = cur.fetchone()[0]
            
        conn.close()
    return render_template('admin_dashboard.html', class_name=CLASS_NAME, active_session=active_session, stats=dashboard_stats)

@app.route('/api/session/start', methods=['POST'])
def start_session():
    if session.get('role') != 'controller': return jsonify({'success': False})
    data = request.json
    admin_lat, admin_lon = data.get('lat'), data.get('lon')

    if not admin_lat or not admin_lon: return jsonify({'success': False, 'message': 'GPS required.'})

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            token = secrets.token_hex(4)
            cur.execute("""INSERT INTO attendance_sessions (class_id, controller_id, session_token, start_time, end_time, session_lat, session_lon) 
                        VALUES (%s, %s, %s, NOW(), NOW() + interval '5 minutes', %s, %s)""", 
                        (class_id, session['user_id'], token, admin_lat, admin_lon))
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

# --- Edit / Manual Mark Routes ---

@app.route('/controller/edit_attendance')
def edit_attendance_days():
    if session.get('role') != 'controller': return redirect(url_for('controller_login'))
    conn = get_db()
    days = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            cur.execute("""
                SELECT DISTINCT DATE(start_time AT TIME ZONE 'UTC') as day 
                FROM attendance_sessions 
                WHERE class_id = %s 
                ORDER BY day DESC
            """, (class_id,))
            days = [row['day'] for row in cur.fetchall()]
    finally: conn.close()
    return render_template('edit_attendance_day_select.html', class_name=CLASS_NAME, session_days=days)

@app.route('/controller/edit_attendance/<date_str>')
def edit_attendance_for_day(date_str):
    if session.get('role') != 'controller': return redirect(url_for('controller_login'))
    conn = get_db()
    data = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            
            cur.execute("SELECT id, name, enrollment_no FROM students ORDER BY enrollment_no")
            students = cur.fetchall()
            
            cur.execute("SELECT id FROM attendance_sessions WHERE class_id = %s AND DATE(start_time AT TIME ZONE 'UTC') = %s", (class_id, date_str))
            session_ids = [row['id'] for row in cur.fetchall()]
            
            present_student_ids = set()
            if session_ids:
                cur.execute("SELECT student_id FROM attendance_records WHERE session_id = ANY(%s)", (session_ids,))
                present_student_ids = {row['student_id'] for row in cur.fetchall()}
                
            for s in students:
                data.append({'id': s['id'], 'name': s['name'], 'roll': s['enrollment_no'], 'present': s['id'] in present_student_ids})
    finally: conn.close()
    return render_template('edit_attendance_for_day.html', class_name=CLASS_NAME, attendance_date=date_str, students=data)

@app.route('/api/update_daily_attendance', methods=['POST'])
def update_daily_attendance():
    if session.get('role') != 'controller': return jsonify({'success': False})
    data = request.json
    date_str, student_id, is_present = data.get('date'), data.get('student_id'), data.get('is_present')
    
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            cur.execute("SELECT id FROM attendance_sessions WHERE class_id = %s AND DATE(start_time AT TIME ZONE 'UTC') = %s", (class_id, date_str))
            result = cur.fetchall()
            
            if not result: return jsonify({'success': False, 'message': 'No session record found.'})
            target_session_id = result[0][0]
            
            if is_present:
                cur.execute("INSERT INTO attendance_records (session_id, student_id, timestamp, ip_address) VALUES (%s, %s, NOW(), 'Manual Edit') ON CONFLICT (session_id, student_id) DO NOTHING", (target_session_id, student_id))
            else:
                session_ids = [r[0] for r in result]
                cur.execute("DELETE FROM attendance_records WHERE student_id = %s AND session_id = ANY(%s)", (student_id, session_ids))
                
            conn.commit()
            return jsonify({'success': True})
    finally: conn.close()

# --- Manual Mark (Current Session) ---
@app.route('/api/get_students_for_manual_edit/<int:session_id>')
def get_students_manual(session_id):
    if session.get('role') != 'controller': return jsonify({'success': False})
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, name, enrollment_no FROM students ORDER BY enrollment_no")
            all_students = cur.fetchall()
            cur.execute("SELECT student_id FROM attendance_records WHERE session_id = %s", (session_id,))
            present_ids = {row['student_id'] for row in cur.fetchall()}
            student_list = [{'id': s['id'], 'name': s['name'], 'enrollment_no': s['enrollment_no'], 'is_present': s['id'] in present_ids} for s in all_students]
            return jsonify({'success': True, 'students': student_list})
    finally: conn.close()

@app.route('/api/manual_mark_attendance', methods=['POST'])
def manual_mark_attendance():
    if session.get('role') != 'controller': return jsonify({'success': False})
    data = request.json
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO attendance_records (session_id, student_id, timestamp, ip_address) VALUES (%s, %s, NOW(), 'Manual') ON CONFLICT DO NOTHING", (data['session_id'], data['student_id']))
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
            
            cur.execute("SELECT DISTINCT DATE(start_time AT TIME ZONE 'UTC') as s_date FROM attendance_sessions WHERE class_id = %s ORDER BY s_date DESC", (class_id,))
            unique_dates = [row['s_date'] for row in cur.fetchall()]
            date_strs = [d.strftime('%d-%b') for d in unique_dates]
            
            cur.execute("SELECT id, name, enrollment_no, batch FROM students ORDER BY batch, enrollment_no")
            students = cur.fetchall()
            
            report_data = []
            for s in students:
                attendance_map = []
                days_present = 0
                for d in unique_dates:
                    cur.execute("SELECT 1 FROM attendance_records r JOIN attendance_sessions ses ON r.session_id = ses.id WHERE r.student_id = %s AND DATE(ses.start_time AT TIME ZONE 'UTC') = %s", (s['id'], d))
                    is_p = cur.fetchone() is not None
                    attendance_map.append('P' if is_p else 'A')
                    if is_p: days_present += 1
                
                total_days = len(unique_dates)
                percent = round((days_present / total_days * 100)) if total_days > 0 else 0
                report_data.append({'name': s['name'], 'roll': s['enrollment_no'], 'batch': s['batch'], 'attendance': attendance_map, 'total_present': days_present, 'percent': percent})
                
            return render_template('attendance_report.html', dates=date_strs, report=report_data, class_name=CLASS_NAME)
    finally: conn.close()

if __name__ == '__main__':
    app.run(port=5000)