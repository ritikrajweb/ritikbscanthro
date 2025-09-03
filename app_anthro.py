import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify, send_file
from functools import wraps
import secrets
import math
import io
import hashlib

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Configuration for the new class ---
CLASS_NAME = 'B.Sc. - Anthro'
BATCH_CODE = 'BSC'
GEOFENCE_RADIUS = 50 # New fixed radius in meters

# Controller login credentials and display name
CONTROLLER_USERNAME = "controller"
CONTROLLER_PASSWORD = "controller_pass_123" # Consider using a different password
CONTROLLER_DISPLAY_NAME = "Anthro Dept Controller"

# Database URL from environment variables
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor().execute("SET TIME ZONE 'UTC';")
        conn.commit()
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

def controller_required(f):
    """Decorator to ensure a user is logged in as the controller."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'controller':
            flash("You must be logged in as the controller to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Helper Functions ---
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates the distance between two GPS coordinates in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
    
def get_class_id_by_name(class_name):
    conn = get_db_connection()
    if conn is None: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM classes WHERE class_name = %s", (class_name,))
            result = cur.fetchone()
            return result[0] if result else None
    finally:
        if conn: conn.close()

def get_controller_id_by_username(username):
    conn = get_db_connection()
    if conn is None: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s AND role = 'controller'", (username,))
            result = cur.fetchone()
            return result[0] if result else None
    finally:
        if conn: conn.close()

def get_active_class_session():
    """Checks for and returns the currently active session for the class."""
    class_id = get_class_id_by_name(CLASS_NAME)
    if not class_id: return None
    conn = get_db_connection()
    if not conn: return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, session_token, start_time, end_time FROM attendance_sessions WHERE class_id = %s AND is_active = TRUE AND end_time > %s ORDER BY start_time DESC LIMIT 1",
                (class_id, datetime.now(timezone.utc))
            )
            session_data = cur.fetchone()
            if not session_data: return None
            
            end_time_utc = session_data['end_time'].astimezone(timezone.utc)
            time_remaining = (end_time_utc - datetime.now(timezone.utc)).total_seconds()
            if time_remaining <= 0:
                cur.execute("UPDATE attendance_sessions SET is_active = FALSE WHERE id = %s", (session_data['id'],))
                conn.commit()
                return None
                
            session_dict = dict(session_data)
            session_dict['class_name'] = CLASS_NAME
            session_dict['remaining_time'] = math.ceil(time_remaining)
            return session_dict
    finally:
        if conn: conn.close()

# --- Main Routes ---
@app.route('/')
def home():
    if 'user_id' in session and session.get('role') == 'controller':
        return redirect(url_for('controller_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == CONTROLLER_USERNAME and password == CONTROLLER_PASSWORD:
            controller_id = get_controller_id_by_username(username)
            if controller_id:
                session['user_id'] = controller_id
                session['username'] = username
                session['role'] = 'controller'
                flash(f"Welcome, {CONTROLLER_DISPLAY_NAME}!", "success")
                return redirect(url_for('controller_dashboard'))
            else:
                flash("Controller user not found in database.", "danger")
        else:
            flash("Invalid username or password.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/mark_attendance', methods=['GET', 'POST'])
def mark_attendance():
    """Handles student attendance marking and displays the correct page state."""
    if request.method == 'POST':
        data = request.form
        required_fields = ['enrollment_no', 'session_id', 'latitude', 'longitude', 'device_fingerprint']
        if not all(field in data and data[field] for field in required_fields):
            return jsonify({"success": False, "message": "Missing required data.", "category": "error"}), 400

        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        conn = get_db_connection()
        if not conn: return jsonify({"success": False, "message": "Database connection failed."}), 500
        
        try:
            with conn.cursor() as cur:
                enrollment_no_upper = data['enrollment_no'].upper()
                cur.execute("SELECT id FROM students WHERE enrollment_no = %s AND batch = %s", (enrollment_no_upper, BATCH_CODE))
                student_result = cur.fetchone()
                if not student_result:
                    return jsonify({"success": False, "message": "Enrollment number not found.", "category": "danger"}), 404
                student_id = student_result[0]

                # UPDATED: Fetch session lat/lon from the session table itself
                cur.execute(
                    "SELECT session_lat, session_lon FROM attendance_sessions WHERE id = %s AND is_active = TRUE AND end_time > %s",
                    (data['session_id'], datetime.now(timezone.utc))
                )
                session_info = cur.fetchone()
                if not session_info or not session_info[0]:
                    return jsonify({"success": False, "message": "Invalid or expired session.", "category": "danger"}), 400

                lat, lon = session_info
                # UPDATED: Use the new fixed radius and compare distance
                distance = haversine_distance(float(data['latitude']), float(data['longitude']), lat, lon)
                if distance > GEOFENCE_RADIUS:
                    return jsonify({"success": False, "message": f"You are {distance:.0f}m away and outside the allowed {GEOFENCE_RADIUS}m radius.", "category": "danger"}), 403

                long_fingerprint = data['device_fingerprint']
                hashed_fingerprint = hashlib.sha256(long_fingerprint.encode('utf-8')).hexdigest()

                cur.execute(
                    "SELECT student_id FROM session_device_fingerprints WHERE session_id = %s AND fingerprint = %s",
                    (data['session_id'], hashed_fingerprint)
                )
                fingerprint_record = cur.fetchone()
                if fingerprint_record and fingerprint_record[0] != student_id:
                    return jsonify({"success": False, "message": "This device has already marked attendance for another student.", "category": "danger"}), 403

                timestamp = datetime.now(timezone.utc)
                cur.execute(
                    "INSERT INTO session_device_fingerprints (session_id, student_id, fingerprint) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (data['session_id'], student_id, hashed_fingerprint)
                )
                cur.execute(
                    "INSERT INTO attendance_records (session_id, student_id, timestamp, latitude, longitude, ip_address) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (session_id, student_id) DO NOTHING",
                    (data['session_id'], student_id, timestamp, float(data['latitude']), float(data['longitude']), ip_address)
                )
                if cur.rowcount == 0:
                    conn.commit()
                    return jsonify({"success": False, "message": "Attendance already marked for this session.", "category": "warning"}), 409

                conn.commit()
                return jsonify({"success": True, "message": "Attendance marked successfully!", "category": "success"})

        except Exception as e:
            conn.rollback()
            print(f"ERROR marking attendance: {e}")
            return jsonify({"success": False, "message": "A server error occurred.", "category": "error"}), 500
        finally:
            if conn: conn.close()

    active_session = get_active_class_session()
    present_students = None
    # UPDATED: Pass geofence data for the active session to the student page
    geofence_data = {'geofence_radius': GEOFENCE_RADIUS}
    todays_date_str = None
    
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                if active_session:
                    cur.execute("SELECT session_lat, session_lon FROM attendance_sessions WHERE id = %s", (active_session['id'],))
                    session_loc = cur.fetchone()
                    if session_loc:
                        geofence_data['geofence_lat'] = session_loc['session_lat']
                        geofence_data['geofence_lon'] = session_loc['session_lon']

                if not active_session:
                    class_id = get_class_id_by_name(CLASS_NAME)
                    if class_id:
                        today_utc = datetime.now(timezone.utc).date()
                        todays_date_str = today_utc.strftime('%B %d, %Y')

                        cur.execute("""
                            SELECT id FROM attendance_sessions
                            WHERE class_id = %s AND DATE(start_time AT TIME ZONE 'UTC') = %s
                        """, (class_id, today_utc))
                        todays_sessions = cur.fetchall()

                        if todays_sessions:
                            session_ids = [s['id'] for s in todays_sessions]
                            cur.execute("""
                                SELECT DISTINCT s.enrollment_no, s.name
                                FROM attendance_records ar
                                JOIN students s ON ar.student_id = s.id
                                WHERE ar.session_id = ANY(%s)
                                ORDER BY s.enrollment_no ASC
                            """, (session_ids,))
                            present_students = cur.fetchall()
        except Exception as e:
            print(f"Error on student page load: {e}")
        finally:
            conn.close()

    return render_template(
        'student_attendance.html',
        active_session=active_session,
        present_students=present_students,
        geofence_data=geofence_data,
        todays_date=todays_date_str,
        class_name=CLASS_NAME
    )

@app.route('/controller_dashboard')
@controller_required
def controller_dashboard():
    active_session = get_active_class_session()
    return render_template('admin_dashboard.html',
                           active_session=active_session,
                           username=session.get('username'),
                           controller_name=CONTROLLER_DISPLAY_NAME,
                           class_name=CLASS_NAME)

@app.route('/start_session', methods=['POST'])
@controller_required
def start_session():
    # UPDATED: Get location from JSON body sent by frontend JS
    data = request.get_json()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if not latitude or not longitude:
        return jsonify({"success": False, "message": "Location data not provided.", "category": "danger"}), 400

    if get_active_class_session():
        return jsonify({"success": False, "message": "An active session already exists.", "category": "info"}), 409
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed.", "category": "danger"}), 500
        
    try:
        with conn.cursor() as cur:
            class_id = get_class_id_by_name(CLASS_NAME)
            if not class_id:
                raise Exception(f"{CLASS_NAME} class not found.")
            start_time = datetime.now(timezone.utc)
            end_time = start_time + timedelta(minutes=5)
            session_token = secrets.token_hex(16)
            # UPDATED: Insert the session's lat/lon into the new columns
            cur.execute(
                "INSERT INTO attendance_sessions (class_id, controller_id, session_token, start_time, end_time, is_active, session_lat, session_lon) VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s) RETURNING id",
                (class_id, session['user_id'], session_token, start_time, end_time, latitude, longitude)
            )
            new_session_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({"success": True, "message": f"New session (ID: {new_session_id}) started!", "category": "success"})
    except Exception as e:
        conn.rollback()
        print(f"ERROR: start_session: {e}")
        return jsonify({"success": False, "message": "Error starting session.", "category": "danger"}), 500
    finally:
        if conn: conn.close()

@app.route('/end_session/<int:session_id>', methods=['POST'])
@controller_required
def end_session(session_id):
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database connection failed."})
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE attendance_sessions SET is_active = FALSE, end_time = %s WHERE id = %s AND controller_id = %s AND is_active = TRUE",
                (datetime.now(timezone.utc), session_id, session['user_id'])
            )
            conn.commit()
            if cur.rowcount > 0:
                return jsonify({"success": True, "message": "Session ended successfully.", "category": "info"})
            else:
                return jsonify({"success": False, "message": "Session not found or already ended.", "category": "warning"})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": "An error occurred."})
    finally:
        if conn: conn.close()

@app.route('/attendance_report')
@controller_required
def attendance_report():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for('controller_dashboard'))
    
    report_data = []
    class_id = get_class_id_by_name(CLASS_NAME)
    if not class_id:
        flash(f"Error: '{CLASS_NAME}' class not found.", "danger")
        return render_template('attendance_report.html', report_data=[], class_name=CLASS_NAME)
        
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, enrollment_no, name FROM students WHERE batch = %s ORDER BY enrollment_no", (BATCH_CODE,))
            all_students = cur.fetchall()
            cur.execute("SELECT id, start_time FROM attendance_sessions WHERE class_id = %s ORDER BY start_time", (class_id,))
            all_sessions = cur.fetchall()

            if all_sessions:
                min_date = min(s['start_time'].date() for s in all_sessions)
                max_date = datetime.now(timezone.utc).date()
                date_range = [min_date + timedelta(days=x) for x in range((max_date - min_date).days + 1)]

                for current_date in date_range:
                    daily_entry = {'date': current_date.strftime('%Y-%m-%d'), 'students': []}
                    sessions_on_date = [s['id'] for s in all_sessions if s['start_time'].date() == current_date]
                    
                    if not sessions_on_date:
                        for student in all_students:
                            daily_entry['students'].append({'name': student['name'], 'enrollment_no': student['enrollment_no'], 'status': 'Holiday'})
                    else:
                        cur.execute("SELECT DISTINCT student_id FROM attendance_records WHERE session_id = ANY(%s)", (sessions_on_date,))
                        attended_student_ids = {row['student_id'] for row in cur.fetchall()}
                        for student in all_students:
                            status = "Present" if student['id'] in attended_student_ids else "Absent"
                            daily_entry['students'].append({'name': student['name'], 'enrollment_no': student['enrollment_no'], 'status': status})
                    
                    report_data.append(daily_entry)
    except Exception as e:
        print(f"ERROR: attendance_report: {e}")
        flash("An error occurred generating the report.", "danger")
    finally:
        if conn: conn.close()
        
    return render_template('attendance_report.html', report_data=report_data, class_name=CLASS_NAME)

@app.route('/delete_daily_attendance', methods=['POST'])
@controller_required
def delete_daily_attendance():
    date_str = request.get_json().get('date')
    if not date_str:
        return jsonify({"success": False, "message": "No date provided."}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed."}), 500
    try:
        with conn.cursor() as cur:
            class_id = get_class_id_by_name(CLASS_NAME)
            date_to_delete = datetime.strptime(date_str, '%Y-%m-%d').date()
            cur.execute(
                "SELECT id FROM attendance_sessions WHERE DATE(start_time AT TIME ZONE 'UTC') = %s AND class_id = %s",
                (date_to_delete, class_id)
            )
            session_ids_to_delete = [row[0] for row in cur.fetchall()]
            if session_ids_to_delete:
                cur.execute("DELETE FROM attendance_sessions WHERE id = ANY(%s)", (session_ids_to_delete,))
                conn.commit()
                return jsonify({"success": True, "message": f"All records for {date_str} deleted.", "category": "success"})
            else:
                return jsonify({"success": True, "message": f"No records found for {date_str}.", "category": "info"})
    except Exception as e:
        conn.rollback()
        print(f"ERROR: delete_daily_attendance: {e}")
        return jsonify({"success": False, "message": "An error occurred."}), 500
    finally:
        if conn: conn.close()

@app.route('/export_attendance_csv')
@controller_required
def export_attendance_csv():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed for export.", "danger")
        return redirect(url_for('attendance_report'))
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            class_id = get_class_id_by_name(CLASS_NAME)
            if not class_id:
                flash(f"Error: Class '{CLASS_NAME}' not found.", "danger")
                return redirect(url_for('attendance_report'))

            cur.execute("SELECT id, enrollment_no, name FROM students WHERE batch = %s ORDER BY enrollment_no ASC", (BATCH_CODE,))
            all_students = cur.fetchall()
            cur.execute("""
                SELECT DISTINCT DATE(start_time AT TIME ZONE 'UTC') AS session_date
                FROM attendance_sessions WHERE class_id = %s ORDER BY session_date ASC
            """, (class_id,))
            session_dates = [row['session_date'] for row in cur.fetchall()]
            
            if not session_dates:
                flash("No attendance sessions found to generate a report.", "info")
                return redirect(url_for('attendance_report'))

            attendance_map = {}
            cur.execute("""
                SELECT ar.student_id, DATE(s.start_time AT TIME ZONE 'UTC') AS session_date
                FROM attendance_records ar JOIN attendance_sessions s ON ar.session_id = s.id
                WHERE s.class_id = %s
            """, (class_id,))
            for record in cur.fetchall():
                attendance_map[(record['student_id'], record['session_date'])] = 'Present'

            output = io.StringIO()
            header = ['Enrollment No', 'Student Name'] + [d.strftime('%Y-%m-%d') for d in session_dates] + ['Total Present', 'Total Classes', 'Percentage']
            output.write(",".join(header) + "\n")

            total_class_days = len(session_dates)

            for student in all_students:
                present_count = 0
                row_data = [student['enrollment_no'], student['name']]
                
                for session_date in session_dates:
                    status = attendance_map.get((student['id'], session_date), 'Absent')
                    row_data.append(status)
                    if status == 'Present':
                        present_count += 1
                
                percentage = (present_count / total_class_days * 100) if total_class_days > 0 else 0
                
                row_data.append(str(present_count))
                row_data.append(str(total_class_days))
                row_data.append(f"{percentage:.2f}%")
                
                output.write(",".join(f'"{item}"' for item in row_data) + "\n")
                
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'Anthro_Semester_Report.csv'
            )

    except Exception as e:
        print(f"ERROR: export_attendance_csv: {e}")
        flash("An error occurred during CSV export.", "danger")
        return redirect(url_for('attendance_report'))
    finally:
        if conn: conn.close()


@app.route('/api/get_student_name/<enrollment_no>')
def api_get_student_name(enrollment_no):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed."}), 500
    try:
        with conn.cursor() as cur:
            enrollment_no_upper = enrollment_no.upper()
            cur.execute("SELECT name FROM students WHERE enrollment_no = %s AND batch = %s", (enrollment_no_upper, BATCH_CODE))
            student_name = cur.fetchone()
            if student_name:
                return jsonify({"success": True, "name": student_name[0]})
            else:
                return jsonify({"success": False, "message": "Student not found."})
    except Exception as e:
        print(f"ERROR: api_get_student_name: {e}")
        return jsonify({"success": False, "message": "An error occurred."}), 500
    finally:
        if conn: conn.close()

# --- NEW/UPDATED ROUTES AND APIS FOR DAILY EDITING ---

@app.route('/edit_attendance_days')
@controller_required
def edit_attendance_days():
    """Page to select which of the last 7 class days to edit."""
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for('controller_dashboard'))
    
    session_days = []
    try:
        with conn.cursor() as cur:
            class_id = get_class_id_by_name(CLASS_NAME)
            cur.execute("""
                SELECT DISTINCT DATE(start_time AT TIME ZONE 'UTC') as class_date
                FROM attendance_sessions
                WHERE class_id = %s
                ORDER BY class_date DESC
                LIMIT 7
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
    """The main page for editing a full day's attendance."""
    try:
        # Validate date format
        day_to_edit = datetime.strptime(date_str, '%Y-%m-%d').date()
        return render_template('edit_attendance_for_day.html', date_to_edit=day_to_edit.strftime('%Y-%m-%d'), class_name=CLASS_NAME)
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(url_for('edit_attendance_days'))


@app.route('/api/get_students_for_day_edit/<date_str>')
@controller_required
def api_get_students_for_day_edit(date_str):
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database failed."}), 500
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            class_id = get_class_id_by_name(CLASS_NAME)
            day_to_query = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            cur.execute("SELECT id, enrollment_no, name FROM students WHERE batch = %s ORDER BY enrollment_no", (BATCH_CODE,))
            all_students = cur.fetchall()
            
            cur.execute("""
                SELECT DISTINCT ar.student_id
                FROM attendance_records ar
                JOIN attendance_sessions s ON ar.session_id = s.id
                WHERE s.class_id = %s AND DATE(s.start_time AT TIME ZONE 'UTC') = %s
            """, (class_id, day_to_query))
            
            present_student_ids = {row['student_id'] for row in cur.fetchall()}
            student_data = [
                {'id': s['id'], 'enrollment_no': s['enrollment_no'], 'name': s['name'], 'is_present': s['id'] in present_student_ids}
                for s in all_students
            ]
            return jsonify({"success": True, "students": student_data})
    except Exception as e:
        print(f"ERROR: api_get_students_for_day_edit: {e}")
        return jsonify({"success": False, "message": "An error occurred."}), 500
    finally:
        if conn: conn.close()


@app.route('/api/update_daily_attendance', methods=['POST'])
@controller_required
def api_update_daily_attendance():
    data = request.get_json()
    date_str = data.get('date')
    student_id = data.get('student_id')
    is_present = data.get('is_present')

    if not all([date_str, student_id, isinstance(is_present, bool)]):
        return jsonify({"success": False, "message": "Missing data."}), 400

    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "message": "Database failed."}), 500

    try:
        with conn.cursor() as cur:
            class_id = get_class_id_by_name(CLASS_NAME)
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            cur.execute(
                "SELECT id FROM attendance_sessions WHERE class_id = %s AND DATE(start_time AT TIME ZONE 'UTC') = %s ORDER BY start_time ASC",
                (class_id, target_date)
            )
            session_ids_for_day = [row[0] for row in cur.fetchall()]

            if not session_ids_for_day:
                return jsonify({"success": False, "message": "No sessions found for this day to edit."}), 404

            if is_present:
                # Add student to the first session of the day to mark them present
                first_session_id = session_ids_for_day[0]
                cur.execute(
                    "INSERT INTO attendance_records (session_id, student_id, timestamp, ip_address) VALUES (%s, %s, %s, 'Manual_Day_Edit') ON CONFLICT DO NOTHING",
                    (first_session_id, student_id, datetime.now(timezone.utc))
                )
            else:
                # Remove student from ALL sessions of that day
                cur.execute(
                    "DELETE FROM attendance_records WHERE student_id = %s AND session_id = ANY(%s)",
                    (student_id, session_ids_for_day)
                )
            conn.commit()
            return jsonify({"success": True, "message": "Attendance updated."})
    except Exception as e:
        conn.rollback()
        print(f"ERROR: api_update_daily_attendance: {e}")
        return jsonify({"success": False, "message": "An error occurred."}), 500
    finally:
        if conn: conn.close()


if __name__ == '__main__':
    # Runs on port 5002 to avoid conflict with the other app
    app.run(debug=True, port=5002)
