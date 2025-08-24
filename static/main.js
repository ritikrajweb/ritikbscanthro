// static/main.js

document.addEventListener('DOMContentLoaded', () => {
    // Check which page we are on and initialize its specific logic
    if (document.getElementById('attendance-form')) {
        console.log('Initializing Student Page Logic...');
        initStudentPage();
    }
    
    if (document.querySelector('.end-session-btn') || document.querySelector('.delete-day-btn')) {
        console.log('Initializing Controller/Report Page Logic...');
        initControllerAndReportPage();
    }

    if (document.getElementById('attendance-table')) {
        console.log('Initializing Edit Attendance Page Logic...');
        initEditAttendancePage();
    }
});

// ==============================================================================
// === STUDENT PAGE LOGIC (with diagnostics) ===
// ==============================================================================
function initStudentPage() {
    const attendanceForm = document.getElementById('attendance-form');
    const markAttendanceButton = document.getElementById('mark-btn');
    const enrollmentNoInput = document.getElementById('enrollment_no');
    const studentNameDisplay = document.getElementById('student-name-display');
    const timerStudentSpan = document.getElementById('timer-student');

    // New diagnostic elements
    const diagnosticPanel = document.getElementById('diagnostic-panel');
    const diagOutput = document.getElementById('diag-output');

    if (!window.activeSessionDataStudent || !window.activeSessionDataStudent.id) {
        console.log('No active session data found on student page.');
        return;
    }

    startStudentTimer(window.activeSessionDataStudent.remaining_time, timerStudentSpan);
    
    enrollmentNoInput.addEventListener('input', debounce(fetchStudentName, 300));
    attendanceForm.addEventListener('submit', handleAttendanceSubmit);

    async function handleAttendanceSubmit(e) {
        e.preventDefault();
        markAttendanceButton.disabled = true;
        markAttendanceButton.textContent = "Processing...";
        showStatusMessage('Getting your location...', 'info');

        // Show the diagnostic panel for debugging
        if (diagnosticPanel) diagnosticPanel.style.display = 'block';

        if (!navigator.geolocation) {
            showStatusMessage('Geolocation is not supported by your browser.', 'error');
            markAttendanceButton.disabled = false;
            markAttendanceButton.textContent = "Mark My Attendance";
            return;
        }

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const { latitude, longitude, accuracy } = position.coords;
                const distance = haversineDistance(latitude, longitude, window.geofenceData.geofence_lat, window.geofenceData.geofence_lon);

                // Display diagnostic information
                if (diagOutput) {
                    diagOutput.innerHTML = `
                        Target Lat: ${window.geofenceData.geofence_lat}<br>
                        Target Lon: ${window.geofenceData.geofence_lon}<br>
                        <hr>
                        Your Lat: ${latitude.toFixed(6)}<br>
                        Your Lon: ${longitude.toFixed(6)}<br>
                        GPS Accuracy: ${accuracy.toFixed(0)} meters<br>
                        <hr>
                        Calculated Distance: <strong>${distance.toFixed(0)} meters</strong><br>
                        Required Radius: <strong>${window.geofenceData.geofence_radius} meters</strong>
                    `;
                }

                if (distance > window.geofenceData.geofence_radius) {
                    showStatusMessage(`You are ${distance.toFixed(0)}m away and outside the allowed radius.`, 'error');
                    markAttendanceButton.disabled = false;
                    markAttendanceButton.textContent = "Mark My Attendance";
                    return;
                }

                // If inside radius, proceed with submission
                // **FIX STARTS HERE**
                let data = { success: false }; // Declare 'data' here with a default value

                try {
                    const visitorId = getCanvasFingerprint();
                    
                    const formData = new URLSearchParams({
                        enrollment_no: enrollmentNoInput.value.trim().toUpperCase(),
                        session_id: window.activeSessionDataStudent.id,
                        latitude: latitude,
                        longitude: longitude,
                        device_fingerprint: visitorId
                    });

                    const response = await fetch('/mark_attendance', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: formData
                    });

                    data = await response.json(); // Assign the response data here
                    showStatusMessage(data.message, data.category);

                    if (data.success) {
                        enrollmentNoInput.value = '';
                        studentNameDisplay.textContent = '';
                        attendanceForm.style.display = 'none'; // Hide form on success
                    }
                } catch (error) {
                    console.error('Error during submission process:', error);
                    showStatusMessage('An unexpected error occurred.', 'error');
                } finally {
                    // 'data' is now accessible here because it was declared outside the try block
                    if (!data.success) {
                        markAttendanceButton.disabled = false;
                        markAttendanceButton.textContent = "Mark My Attendance";
                    }
                }
                // **FIX ENDS HERE**
            },
            (geoError) => {
                showStatusMessage('Geolocation error: ' + geoError.message, 'error');
                if (diagOutput) diagOutput.textContent = `Geolocation Error: ${geoError.message}. Please ensure you have enabled location services for your browser.`;
                markAttendanceButton.disabled = false;
                markAttendanceButton.textContent = "Mark My Attendance";
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    }

    async function fetchStudentName() {
        const enrollmentNo = enrollmentNoInput.value.trim();
        if (enrollmentNo.length >= 5) {
            try {
                const response = await fetch(`/api/get_student_name/${enrollmentNo}`);
                const data = await response.json();
                studentNameDisplay.textContent = data.name ? `Name: ${data.name}` : 'Student not found.';
                studentNameDisplay.style.color = data.name ? '#0056b3' : '#dc3545';
            } catch (error) {
                studentNameDisplay.textContent = 'Error fetching name.';
            }
        } else {
            studentNameDisplay.textContent = '';
        }
    }
}

// ==============================================================================
// === CONTROLLER, REPORT, & EDIT PAGE LOGIC (Unchanged) ===
// ==============================================================================
function initControllerAndReportPage() {
    const confirmationModal = document.getElementById('confirmation-modal');
    const confirmMessage = document.getElementById('confirm-message');
    const confirmYesBtn = document.getElementById('confirm-yes');
    const confirmNoBtn = document.getElementById('confirm-no');
    const modalCloseBtn = confirmationModal ? confirmationModal.querySelector('.close-button') : null;
    let pendingDeleteDate = null;
    function showConfirmationModal(message, dataToConfirm) { if (confirmationModal && confirmMessage) { confirmMessage.textContent = message; pendingDeleteDate = dataToConfirm; confirmationModal.style.display = 'block'; } }
    function hideConfirmationModal() { if (confirmationModal) { confirmationModal.style.display = 'none'; } }
    if (modalCloseBtn) modalCloseBtn.addEventListener('click', hideConfirmationModal);
    if (confirmNoBtn) confirmNoBtn.addEventListener('click', hideConfirmationModal);
    window.addEventListener('click', (event) => { if (event.target == confirmationModal) hideConfirmationModal(); });
    if (confirmYesBtn) { confirmYesBtn.addEventListener('click', async () => { const dateToProcess = pendingDeleteDate; hideConfirmationModal(); if (dateToProcess) { await deleteDailyAttendance(dateToProcess); } pendingDeleteDate = null; }); }
    document.querySelectorAll('.end-session-btn').forEach(button => { button.addEventListener('click', async function() { const sessionId = this.dataset.sessionId; showStatusMessage('Ending session...', 'info'); try { const response = await fetch(`/end_session/${sessionId}`, { method: 'POST' }); const data = await response.json(); showStatusMessage(data.message, data.category); if (data.success) { setTimeout(() => window.location.reload(), 1000); } } catch (error) { showStatusMessage('An error occurred while ending the session.', 'error'); } }); });
    if (typeof window.activeSessionData !== 'undefined' && window.activeSessionData.id) { let remainingTime = window.activeSessionData.remaining_time; let timerDisplay = document.getElementById(`timer-${window.activeSessionData.id}`); if (timerDisplay && remainingTime > 0) { let controllerTimer = setInterval(() => { remainingTime--; if (remainingTime <= 0) { clearInterval(controllerTimer); window.location.reload(); } let minutes = Math.floor(remainingTime / 60); let seconds = remainingTime % 60; timerDisplay.innerHTML = `${minutes}m ${seconds}s`; }, 1000); } }
    document.body.addEventListener('click', function(event) { if (event.target && event.target.classList.contains('delete-day-btn')) { const dateToDelete = event.target.dataset.date; showConfirmationModal(`Are you sure you want to delete all attendance records for ${dateToDelete}? This action cannot be undone.`, dateToDelete); } });
    async function deleteDailyAttendance(date) { showStatusMessage(`Deleting attendance for ${date}...`, 'info'); try { const response = await fetch('/delete_daily_attendance', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date: date }) }); const data = await response.json(); showStatusMessage(data.message, data.category); if (data.success) { setTimeout(() => window.location.reload(), 1000); } } catch (error) { showStatusMessage('A network error occurred during deletion.', 'error'); } }
}

function initEditAttendancePage() {
    const editAttendanceTable = document.getElementById('attendance-table');
    const sessionId = editAttendanceTable.dataset.sessionId;
    async function fetchStudentsForEdit(sessionId) { const tbody = editAttendanceTable.querySelector('tbody'); tbody.innerHTML = '<tr><td colspan="3">Loading students...</td></tr>'; try { const response = await fetch(`/api/get_session_students_for_edit/${sessionId}`); const data = await response.json(); if (!data.success || !data.students) { tbody.innerHTML = `<tr><td colspan="3">${data.message || 'Failed to load students.'}</td></tr>`; return; } tbody.innerHTML = ''; data.students.forEach(student => { const row = tbody.insertRow(); row.innerHTML = `<td>${student.enrollment_no}</td><td>${student.name}</td><td><input type="checkbox" data-student-id="${student.id}" class="attendance-checkbox" ${student.is_present ? 'checked' : ''}></td>`; }); tbody.querySelectorAll('.attendance-checkbox').forEach(checkbox => { checkbox.addEventListener('change', function() { const studentId = this.dataset.studentId; const isPresent = this.checked; updateAttendanceRecord(sessionId, studentId, isPresent, this); }); }); } catch (error) { tbody.innerHTML = '<tr><td colspan="3">An unexpected error occurred.</td></tr>'; } }
    async function updateAttendanceRecord(sessionId, studentId, isPresent, checkboxElement) { showStatusMessage('Updating attendance...', 'info'); try { const response = await fetch('/api/update_attendance_record', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, student_id: studentId, is_present: isPresent }) }); const data = await response.json(); showStatusMessage(data.message, data.success ? 'success' : 'error'); if (!data.success) { checkboxElement.checked = !isPresent; } } catch (error) { showStatusMessage('An error occurred while updating.', 'error'); checkboxElement.checked = !isPresent; } }
    fetchStudentsForEdit(sessionId);
}


// ==============================================================================
// === UTILITY FUNCTIONS (Unchanged) ===
// ==============================================================================
function getCanvasFingerprint() {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const txt = 'Browser-ID: Ritik Attendance App';
    ctx.textBaseline = "top";
    ctx.font = "14px 'Arial'";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = "#f60";
    ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = "#069";
    ctx.fillText(txt, 2, 15);
    ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
    ctx.fillText(txt, 4, 17);
    return canvas.toDataURL();
}

function startStudentTimer(remainingTime, timerElement) { if (!timerElement || remainingTime <= 0) return; let timer = setInterval(() => { remainingTime--; if (remainingTime <= 0) { clearInterval(timer); timerElement.innerHTML = "Session ended."; const markBtn = document.getElementById('mark-btn'); if(markBtn) markBtn.disabled = true; return; } let minutes = Math.floor(remainingTime / 60); let seconds = remainingTime % 60; timerElement.innerHTML = `${minutes}m ${seconds}s`; }, 1000); }
function showStatusMessage(message, type) { const statusMessageDiv = document.getElementById('status-message'); if (statusMessageDiv) { statusMessageDiv.textContent = message; statusMessageDiv.className = `status-message ${type}`; statusMessageDiv.style.display = 'block'; setTimeout(() => { statusMessageDiv.style.display = 'none'; }, 5000); } }
function haversineDistance(lat1, lon1, lat2, lon2) { const R = 6371e3; const φ1 = lat1 * Math.PI / 180; const φ2 = lat2 * Math.PI / 180; const Δφ = (lat2 - lat1) * Math.PI / 180; const Δλ = (lon2 - lon1) * Math.PI / 180; const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2); const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)); return R * c; }
function debounce(func, delay) { let timeout; return function(...args) { clearTimeout(timeout); timeout = setTimeout(() => func.apply(this, args), delay); }; }
