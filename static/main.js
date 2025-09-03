// static/main.js

document.addEventListener('DOMContentLoaded', () => {
    // Check which page we are on and initialize its specific logic
    if (document.getElementById('attendance-form')) {
        console.log('Initializing Student Page Logic...');
        initStudentPage();
    }
    
    // Updated condition to include the new start session button
    if (document.querySelector('.end-session-btn') || document.querySelector('.delete-day-btn') || document.getElementById('start-session-btn')) {
        console.log('Initializing Controller/Report Page Logic...');
        initControllerAndReportPage();
    }

    // NEW: Check for the daily edit table
    if (document.getElementById('attendance-table-daily')) {
        console.log('Initializing Edit Daily Attendance Page Logic...');
        initEditDailyAttendancePage();
    }
});

// ==============================================================================
// === STUDENT PAGE LOGIC ===
// ==============================================================================
function initStudentPage() {
    const attendanceForm = document.getElementById('attendance-form');
    const markAttendanceButton = document.getElementById('mark-btn');
    const enrollmentNoInput = document.getElementById('enrollment_no');
    const studentNameDisplay = document.getElementById('student-name-display');
    const timerStudentSpan = document.getElementById('timer-student');

    // This check is safe because it handles the null case correctly
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

        if (!navigator.geolocation) {
            showStatusMessage('Geolocation is not supported by your browser.', 'error');
            markAttendanceButton.disabled = false;
            markAttendanceButton.textContent = "Mark My Attendance";
            return;
        }

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const { latitude, longitude } = position.coords;
                
                let data = { success: false };

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

                    data = await response.json(); 
                    showStatusMessage(data.message, data.category);

                    if (data.success) {
                        enrollmentNoInput.value = '';
                        studentNameDisplay.textContent = '';
                        attendanceForm.style.display = 'none';
                    }
                } catch (error) {
                    console.error('Error during submission process:', error);
                    showStatusMessage('An unexpected error occurred.', 'error');
                } finally {
                    if (!data.success) {
                        markAttendanceButton.disabled = false;
                        markAttendanceButton.textContent = "Mark My Attendance";
                    }
                }
            },
            (geoError) => {
                showStatusMessage('Geolocation error: ' + geoError.message, 'error');
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
// === CONTROLLER & REPORT PAGE LOGIC ===
// ==============================================================================
function initControllerAndReportPage() {
    const startSessionBtn = document.getElementById('start-session-btn');
    const confirmationModal = document.getElementById('confirmation-modal');
    const confirmMessage = document.getElementById('confirm-message');
    const confirmYesBtn = document.getElementById('confirm-yes');
    const confirmNoBtn = document.getElementById('confirm-no');
    const modalCloseBtn = confirmationModal ? confirmationModal.querySelector('.close-button') : null;
    let pendingDeleteDate = null;

    if (startSessionBtn) {
        startSessionBtn.addEventListener('click', function() {
            this.disabled = true;
            this.textContent = 'Getting Location...';
            showStatusMessage('Please allow location access to start the session.', 'info');

            if (!navigator.geolocation) {
                showStatusMessage('Geolocation is not supported by your browser.', 'error');
                this.disabled = false;
                this.textContent = 'Start New 5-Minute Session';
                return;
            }

            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    const { latitude, longitude } = position.coords;
                    showStatusMessage('Location acquired. Starting session...', 'info');
                    try {
                        const response = await fetch('/start_session', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ latitude: latitude, longitude: longitude })
                        });
                        const data = await response.json();
                        showStatusMessage(data.message, data.category);
                        if (data.success) {
                            setTimeout(() => window.location.reload(), 1500);
                        } else {
                            this.disabled = false;
                            this.textContent = 'Start New 5-Minute Session';
                        }
                    } catch (error) {
                        showStatusMessage('A network error occurred while starting the session.', 'error');
                        this.disabled = false;
                        this.textContent = 'Start New 5-Minute Session';
                    }
                },
                (geoError) => {
                    showStatusMessage(`Geolocation error: ${geoError.message}.`, 'error');
                    this.disabled = false;
                    this.textContent = 'Start New 5-Minute Session';
                },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
            );
        });
    }

    function showConfirmationModal(message, dataToConfirm) { if (confirmationModal && confirmMessage) { confirmMessage.textContent = message; pendingDeleteDate = dataToConfirm; confirmationModal.style.display = 'block'; } }
    function hideConfirmationModal() { if (confirmationModal) { confirmationModal.style.display = 'none'; } }
    if (modalCloseBtn) modalCloseBtn.addEventListener('click', hideConfirmationModal);
    if (confirmNoBtn) confirmNoBtn.addEventListener('click', hideConfirmationModal);
    window.addEventListener('click', (event) => { if (event.target == confirmationModal) hideConfirmationModal(); });
    if (confirmYesBtn) { confirmYesBtn.addEventListener('click', async () => { const dateToProcess = pendingDeleteDate; hideConfirmationModal(); if (dateToProcess) { await deleteDailyAttendance(dateToProcess); } pendingDeleteDate = null; }); }
    document.querySelectorAll('.end-session-btn').forEach(button => { button.addEventListener('click', async function() { const sessionId = this.dataset.sessionId; showStatusMessage('Ending session...', 'info'); try { const response = await fetch(`/end_session/${sessionId}`, { method: 'POST' }); const data = await response.json(); showStatusMessage(data.message, data.category); if (data.success) { setTimeout(() => window.location.reload(), 1000); } } catch (error) { showStatusMessage('An error occurred while ending the session.', 'error'); } }); });
    
    // ** THE FIX IS HERE **
    // This condition now safely checks if window.activeSessionData is a valid object before trying to access its properties.
    if (window.activeSessionData && window.activeSessionData.id) { 
        let remainingTime = window.activeSessionData.remaining_time; 
        let timerDisplay = document.getElementById(`timer-${window.activeSessionData.id}`); 
        if (timerDisplay && remainingTime > 0) { 
            let controllerTimer = setInterval(() => { 
                remainingTime--; 
                if (remainingTime <= 0) { 
                    clearInterval(controllerTimer); 
                    window.location.reload(); 
                } 
                let minutes = Math.floor(remainingTime / 60); 
                let seconds = remainingTime % 60; 
                timerDisplay.innerHTML = `${minutes}m ${seconds}s`; 
            }, 1000); 
        } 
    }

    document.body.addEventListener('click', function(event) { if (event.target && event.target.classList.contains('delete-day-btn')) { const dateToDelete = event.target.dataset.date; showConfirmationModal(`Are you sure you want to delete all attendance records for ${dateToDelete}? This action cannot be undone.`, dateToDelete); } });
    async function deleteDailyAttendance(date) { showStatusMessage(`Deleting attendance for ${date}...`, 'info'); try { const response = await fetch('/delete_daily_attendance', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date: date }) }); const data = await response.json(); showStatusMessage(data.message, data.category); if (data.success) { setTimeout(() => window.location.reload(), 1000); } } catch (error) { showStatusMessage('A network error occurred during deletion.', 'error'); } }
}

// ==============================================================================
// === NEW: EDIT DAILY ATTENDANCE PAGE LOGIC ===
// ==============================================================================
function initEditDailyAttendancePage() {
    const dailyAttendanceTable = document.getElementById('attendance-table-daily');
    const dateToEdit = dailyAttendanceTable.dataset.date;

    async function fetchStudentsForDayEdit(date) {
        const tbody = dailyAttendanceTable.querySelector('tbody');
        tbody.innerHTML = '<tr><td colspan="3">Loading students...</td></tr>';
        try {
            const response = await fetch(`/api/get_students_for_day_edit/${date}`);
            const data = await response.json();
            if (!data.success || !data.students) {
                tbody.innerHTML = `<tr><td colspan="3">${data.message || 'Failed to load students.'}</td></tr>`;
                return;
            }
            tbody.innerHTML = '';
            data.students.forEach(student => {
                const row = tbody.insertRow();
                row.innerHTML = `<td>${student.enrollment_no}</td><td>${student.name}</td><td><input type="checkbox" data-student-id="${student.id}" class="attendance-checkbox" ${student.is_present ? 'checked' : ''}></td>`;
            });
            tbody.querySelectorAll('.attendance-checkbox').forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const studentId = this.dataset.studentId;
                    const isPresent = this.checked;
                    updateDailyAttendanceRecord(date, studentId, isPresent, this);
                });
            });
        } catch (error) {
            tbody.innerHTML = '<tr><td colspan="3">An unexpected error occurred.</td></tr>';
        }
    }

    async function updateDailyAttendanceRecord(date, studentId, isPresent, checkboxElement) {
        showStatusMessage('Updating attendance...', 'info');
        try {
            const response = await fetch('/api/update_daily_attendance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    date: date,
                    student_id: studentId,
                    is_present: isPresent
                })
            });
            const data = await response.json();
            showStatusMessage(data.message, data.success ? 'success' : 'error');
            if (!data.success) {
                checkboxElement.checked = !isPresent; // Revert checkbox on failure
            }
        } catch (error) {
            showStatusMessage('An error occurred while updating.', 'error');
            checkboxElement.checked = !isPresent;
        }
    }

    fetchStudentsForDayEdit(dateToEdit);
}


// ==============================================================================
// === UTILITY FUNCTIONS (Unchanged) ===
// ==============================================================================
function getCanvasFingerprint() { const canvas = document.createElement('canvas'); const ctx = canvas.getContext('2d'); const txt = 'Browser-ID: Ritik Attendance App'; ctx.textBaseline = "top"; ctx.font = "14px 'Arial'"; ctx.textBaseline = "alphabetic"; ctx.fillStyle = "#f60"; ctx.fillRect(125, 1, 62, 20); ctx.fillStyle = "#069"; ctx.fillText(txt, 2, 15); ctx.fillStyle = "rgba(102, 204, 0, 0.7)"; ctx.fillText(txt, 4, 17); return canvas.toDataURL(); }
function startStudentTimer(remainingTime, timerElement) { if (!timerElement || remainingTime <= 0) return; let timer = setInterval(() => { remainingTime--; if (remainingTime <= 0) { clearInterval(timer); timerElement.innerHTML = "Session ended."; const markBtn = document.getElementById('mark-btn'); if(markBtn) markBtn.disabled = true; return; } let minutes = Math.floor(remainingTime / 60); let seconds = remainingTime % 60; timerElement.innerHTML = `${minutes}m ${seconds}s`; }, 1000); }
function showStatusMessage(message, type) { const statusMessageDiv = document.getElementById('status-message'); if (statusMessageDiv) { statusMessageDiv.textContent = message; statusMessageDiv.className = `status-message ${type}`; statusMessageDiv.style.display = 'block'; setTimeout(() => { statusMessageDiv.style.display = 'none'; }, 5000); } }
function haversineDistance(lat1, lon1, lat2, lon2) { const R = 6371e3; const φ1 = lat1 * Math.PI / 180; const φ2 = lat2 * Math.PI / 180; const Δφ = (lat2 - lat1) * Math.PI / 180; const Δλ = (lon2 - lon1) * Math.PI / 180; const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2); const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)); return R * c; }
function debounce(func, delay) { let timeout; return function(...args) { clearTimeout(timeout); timeout = setTimeout(() => func.apply(this, args), delay); }; }

