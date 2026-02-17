import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from functools import wraps
import secrets
import math

app = Flask(__name__)
# Security: Change this in production settings on Render
app.secret_key = os.environ.get('SECRET_KEY', 'ritik_crafted_this_securely')

# 1. PERMANENT LOGIN CONFIGURATION (User stays logged in for 1 Year)
app.permanent_session_lifetime = timedelta(days=365)

# --- Configurations ---
CLASS_NAME = 'Practical 4th Sem'
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
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'student_id' not in session and session.get('role') != 'controller':
            return redirect(url_for('student_auth'))
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
            
            # SET PERMANENT SESSION
            session.permanent = True
            session['student_id'] = student['id']
            session['student_name'] = student['name']
            session['student_batch'] = student['batch']
            # Check if student is a monitor (can start sessions)
            session['is_monitor'] = student.get('can_start_session', False)
            
            return jsonify({'success': True})
    finally: conn.close()

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

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if session.get('role') == 'controller': return redirect(url_for('controller_dashboard'))
    
    stats = {'total': 0, 'present': 0, 'percent': 0}
    active_session = None
    conn = get_db()
    
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
                class_id = cur.fetchone()[0]
                
                # Filter stats by the student's batch (BA or BSC)
                student_batch = session.get('student_batch', 'ALL')
                
                cur.execute("""
                    SELECT COUNT(DISTINCT DATE(start_time AT TIME ZONE 'UTC')) 
                    FROM attendance_sessions 
                    WHERE class_id = %s AND is_active = FALSE 
                    AND (batch_filter = 'ALL' OR batch_filter = %s)
                """, (class_id, student_batch))
                stats['total'] = cur.fetchone()[0]
                
                cur.execute("""
                    SELECT COUNT(DISTINCT DATE(s.start_time AT TIME ZONE 'UTC')) 
                    FROM attendance_records r
                    JOIN attendance_sessions s ON r.session_id = s.id
                    WHERE r.student_id = %s AND s.class_id = %s
                """, (session['student_id'], class_id))
                stats['present'] = cur.fetchone()[0]
                
                if stats['total'] > 0: stats['percent'] = round((stats['present'] / stats['total']) * 100)
                
                # Check for active session matching student's batch
                cur.execute("""
                    SELECT * FROM attendance_sessions 
                    WHERE class_id = %s AND is_active = TRUE 
                    AND (batch_filter = 'ALL' OR batch_filter = %s)
                """, (class_id, student_batch))
                sess = cur.fetchone()
                
                if sess:
                    active_session = {'id': sess['id'], 'end_time': sess['end_time'].isoformat(), 'batch': sess['batch_filter']}
                    cur.execute("SELECT 1 FROM attendance_records WHERE session_id = %s AND student_id = %s", (sess['id'], session['student_id']))
                    active_session['marked'] = cur.fetchone() is not None
        finally: conn.close()
    
    return render_template('student_attendance.html', class_name=CLASS_NAME, stats=stats, active_session=active_session, name=session['student_name'], is_monitor=session.get('is_monitor', False))

@app.route('/api/mark', methods=['POST'])
@login_required
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
            
            # Security: Ensure student belongs to the batch of the session
            if sess['batch_filter'] != 'ALL' and sess['batch_filter'] != session.get('student_batch'):
                 return jsonify({'success': False, 'message': f"This session is for {sess['batch_filter']} students only."})

            dist = haversine(lat, lon, sess['session_lat'], sess['session_lon'])
            if dist > GEOFENCE_RADIUS: 
                return jsonify({'success': False, 'message': f'Too far ({int(dist)}m). Move closer.'})
            
            cur.execute("INSERT INTO attendance_records (session_id, student_id, timestamp, latitude, longitude, ip_address) VALUES (%s, %s, NOW(), %s, %s, 'Mobile') ON CONFLICT DO NOTHING",
                       (sid, session['student_id'], lat, lon))
            conn.commit()
            return jsonify({'success': True})
    finally: conn.close()

# --- Controller/Admin Routes ---

@app.route('/login', methods=['GET', 'POST'])
def controller_login():
    if request.method == 'POST':
        if request.form.get('username') == CONTROLLER_USER and request.form.get('password') == CONTROLLER_PASS:
            session.permanent = True
            session['role'] = 'controller'
            session['user_id'] = 1 
            return redirect(url_for('controller_dashboard'))
    return render_template('student_auth.html', class_name=CLASS_NAME, is_admin=True)

@app.route('/controller')
def controller_dashboard():
    if session.get('role') != 'controller': return redirect(url_for('controller_login'))
    
    conn = get_db()
    active_session = None
    dashboard_stats = {'total_classes': 0}
    
    if conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            res = cur.fetchone()
            if res:
                class_id = res[0]
                cur.execute("SELECT id, end_time, batch_filter FROM attendance_sessions WHERE class_id = %s AND is_active = TRUE", (class_id,))
                sess = cur.fetchone()
                if sess: active_session = {'id': sess['id'], 'end_time': sess['end_time'].isoformat(), 'batch': sess['batch_filter']}
                
                cur.execute("SELECT COUNT(DISTINCT DATE(start_time AT TIME ZONE 'UTC')) FROM attendance_sessions WHERE class_id = %s AND is_active = FALSE", (class_id,))
                dashboard_stats['total_classes'] = cur.fetchone()[0]
        conn.close()
    return render_template('admin_dashboard.html', class_name=CLASS_NAME, active_session=active_session, stats=dashboard_stats)

@app.route('/api/session/start', methods=['POST'])
def start_session():
    # Allow Controllers OR Student Monitors to start
    if session.get('role') != 'controller' and not session.get('is_monitor'): 
        return jsonify({'success': False, 'message': 'Unauthorized'})
        
    data = request.json
    admin_lat, admin_lon = data.get('lat'), data.get('lon')
    batch_type = data.get('batch', 'ALL') # 'BA', 'BSC', or 'ALL'

    if not admin_lat or not admin_lon: return jsonify({'success': False, 'message': 'GPS required.'})

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            
            cur.execute("SELECT id FROM attendance_sessions WHERE is_active = TRUE")
            if cur.fetchone(): return jsonify({'success': False, 'message': 'Session already active!'})

            token = secrets.token_hex(4)
            # Controller ID is NULL for student monitors (anonymous start)
            controller_id = session.get('user_id') if session.get('role') == 'controller' else None 
            
            cur.execute("""INSERT INTO attendance_sessions (class_id, controller_id, session_token, start_time, end_time, session_lat, session_lon, is_active, batch_filter) 
                        VALUES (%s, %s, %s, NOW(), NOW() + interval '5 minutes', %s, %s, TRUE, %s)""", 
                        (class_id, controller_id, token, admin_lat, admin_lon, batch_type))
            conn.commit()
            return jsonify({'success': True})
    finally: conn.close()

@app.route('/api/session/end', methods=['POST'])
def end_session():
    # Monitors can also end session
    if session.get('role') != 'controller' and not session.get('is_monitor'): return jsonify({'success': False})
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE attendance_sessions SET is_active = FALSE WHERE is_active = TRUE")
            conn.commit()
            return jsonify({'success': True})
    finally: conn.close()

# --- OPTIMIZED REPORT & EDIT ---

@app.route('/controller/edit_attendance')
def edit_attendance_landing():
    if session.get('role') != 'controller': return redirect(url_for('controller_login'))
    return render_template('edit_attendance_day_select.html', class_name=CLASS_NAME)

@app.route('/controller/edit_attendance/<date_str>')
def edit_attendance_for_day(date_str):
    if session.get('role') != 'controller': return redirect(url_for('controller_login'))
    conn = get_db()
    data = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (CLASS_NAME,))
            class_id = cur.fetchone()[0]
            
            # Find all session IDs for that date
            cur.execute("""
                SELECT id FROM attendance_sessions 
                WHERE class_id = %s AND DATE(start_time AT TIME ZONE 'UTC') = %s
            """, (class_id, date_str))
            session_ids = [row['id'] for row in cur.fetchall()]
            
            # Fetch students and check if they were present in ANY session on that day
            cur.execute("""
                SELECT s.id, s.name, s.enrollment_no, s.batch,
                       CASE WHEN r.session_id IS NOT NULL THEN TRUE ELSE FALSE END as present
                FROM students s
                LEFT JOIN attendance_records r ON s.id = r.student_id AND r.session_id = ANY(%s)
                ORDER BY s.enrollment_no
            """, (session_ids,))
            
            students = cur.fetchall()
            data = [{'id': s['id'], 'name': s['name'], 'roll': s['enrollment_no'], 'batch': s['batch'], 'present': s['present']} for s in students]
            
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
            
            # Find ANY existing session
            cur.execute("SELECT id FROM attendance_sessions WHERE class_id = %s AND DATE(start_time AT TIME ZONE 'UTC') = %s LIMIT 1", (class_id, date_str))
            res = cur.fetchone()
            
            if res:
                target_session_id = res[0]
            else:
                # If no session existed, create a "Dummy/Manual" session so we can attach the record
                cur.execute("""
                    INSERT INTO attendance_sessions (class_id, controller_id, session_token, start_time, end_time, is_active, batch_filter)
                    VALUES (%s, %s, 'MANUAL_EDIT', %s::date + interval '12 hours', %s::date + interval '12 hours', FALSE, 'ALL')
                    RETURNING id
                """, (class_id, session['user_id'], date_str, date_str))
                target_session_id = cur.fetchone()[0]

            if is_present:
                cur.execute("INSERT INTO attendance_records (session_id, student_id, timestamp, ip_address) VALUES (%s, %s, NOW(), 'Manual Edit') ON CONFLICT (session_id, student_id) DO NOTHING", (target_session_id, student_id))
            else:
                cur.execute("""
                    DELETE FROM attendance_records 
                    WHERE student_id = %s AND session_id IN (
                        SELECT id FROM attendance_sessions WHERE class_id = %s AND DATE(start_time AT TIME ZONE 'UTC') = %s
                    )
                """, (student_id, class_id, date_str))
                
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
            
            # Get Dates
            cur.execute("SELECT DISTINCT DATE(start_time AT TIME ZONE 'UTC') as s_date FROM attendance_sessions WHERE class_id = %s ORDER BY s_date DESC", (class_id,))
            dates = [row['s_date'].strftime('%Y-%m-%d') for row in cur.fetchall()]
            
            # FAST QUERY: Get all attendance at once
            cur.execute("""
                SELECT s.name, s.enrollment_no, s.batch,
                       ARRAY_AGG(DISTINCT DATE(ses.start_time AT TIME ZONE 'UTC')) FILTER (WHERE r.session_id IS NOT NULL) as present_dates
                FROM students s
                LEFT JOIN attendance_records r ON s.id = r.student_id
                LEFT JOIN attendance_sessions ses ON r.session_id = ses.id AND ses.class_id = %s
                GROUP BY s.id
                ORDER BY s.batch, s.enrollment_no
            """, (class_id,))
            
            students = cur.fetchall()
            
            report_data = []
            for s in students:
                present_set = set([d.strftime('%Y-%m-%d') for d in s['present_dates']]) if s['present_dates'] else set()
                attendance_map = []
                days_present = 0
                for d in dates:
                    if d in present_set:
                        attendance_map.append('P')
                        days_present += 1
                    else:
                        attendance_map.append('A')
                
                total = len(dates)
                percent = round((days_present / total * 100)) if total > 0 else 0
                report_data.append({
                    'name': s['name'], 'roll': s['enrollment_no'], 'batch': s['batch'],
                    'attendance': attendance_map, 'total_present': days_present, 'percent': percent
                })

            return render_template('attendance_report.html', dates=[d[5:] for d in dates], full_dates=dates, report=report_data, class_name=CLASS_NAME)
    finally: conn.close()

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

@app.route('/student/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(port=5000)