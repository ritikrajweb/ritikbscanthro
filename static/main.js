/**
 * Main Logic for Practical 4th Sem Attendance System
 * Handles: Auth, Geolocation, Admin Controls, and Manual Editing
 */

// --- UTILITIES ---

function showMsg(txt, type='error') {
    let el = document.getElementById('status-message');
    if (!el) {
        // Create message box if it doesn't exist (fallback)
        el = document.createElement('div');
        el.id = 'status-message';
        document.body.prepend(el);
    }
    el.textContent = txt; 
    el.className = `status-message ${type}`; 
    el.style.display = 'block';
    
    // Auto-hide after 4 seconds
    setTimeout(() => { 
        el.style.display = 'none'; 
    }, 4000);
}

// Generate or retrieve a unique Device ID for locking accounts
function getDevId() {
    let id = localStorage.getItem('did');
    if(!id) { 
        id = 'dev_' + Math.random().toString(36).substr(2,9) + Date.now().toString(36); 
        localStorage.setItem('did', id); 
    }
    return id;
}

// Toggle between Login and Register forms
function toggle() {
    document.getElementById('login-form').classList.toggle('hidden');
    document.getElementById('register-form').classList.toggle('hidden');
}

// --- AUTHENTICATION ---

async function auth(e, type) {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    const originalText = btn.textContent;
    btn.disabled = true; 
    btn.textContent = "Processing...";
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    data.device_id = getDevId(); // Attach Device ID
    
    try {
        const res = await fetch(`/api/student/${type}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const json = await res.json();
        
        if(json.success) {
            if(type === 'register') {
                showMsg('Registration Successful! Logging in...', 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                window.location.href = '/student/dashboard';
            }
        } else {
            showMsg(json.message, 'error');
            btn.disabled = false; 
            btn.textContent = originalText;
        }
    } catch(err) {
        showMsg("Connection failed. Check internet.", 'error');
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// --- STUDENT ATTENDANCE MARKING ---

function mark(sid) {
    const btn = document.getElementById('mark-btn');
    const txt = document.getElementById('gps-status');
    const originalText = btn.textContent;
    
    btn.disabled = true; 
    btn.textContent = "Locating...";
    
    if(!navigator.geolocation) { 
        showMsg("GPS is not supported on this device.", 'error'); 
        btn.disabled = false;
        return; 
    }
    
    const options = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
    };

    navigator.geolocation.getCurrentPosition(async (pos) => {
        btn.textContent = "Verifying...";
        try {
            const res = await fetch('/api/mark', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    lat: pos.coords.latitude,
                    lon: pos.coords.longitude,
                    session_id: sid
                })
            });
            const json = await res.json();
            
            if(json.success) {
                showMsg("Attendance Marked Successfully!", 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showMsg(json.message, 'error');
                btn.disabled = false; 
                btn.textContent = originalText;
                if(txt) txt.textContent = json.message;
            }
        } catch(e) { 
            showMsg("Server Connection Error", 'error'); 
            btn.disabled = false; 
            btn.textContent = originalText;
        }
    }, (err) => {
        console.error(err);
        let errorMsg = "Location access denied.";
        if(err.code === 1) errorMsg = "Please allow Location Access in browser settings.";
        else if(err.code === 2) errorMsg = "Position unavailable. Try moving outside.";
        else if(err.code === 3) errorMsg = "GPS timeout. Try again.";
        
        showMsg(errorMsg, 'error');
        btn.disabled = false;
        btn.textContent = "Retry Attendance";
    }, options);
}

// --- ADMIN CONTROLS ---

async function startSession() {
    if(!confirm("Start 5 minute session? This will set the class location to where you are standing NOW (80m radius).")) return;
    
    const btn = document.querySelector('button[onclick="startSession()"]');
    if(btn) { btn.disabled = true; btn.textContent = "Acquiring Admin GPS..."; }

    if (!navigator.geolocation) {
        alert("Geolocation is not supported by your browser.");
        if(btn) btn.disabled = false;
        return;
    }

    navigator.geolocation.getCurrentPosition(async (pos) => {
        try {
            const res = await fetch('/api/session/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    lat: pos.coords.latitude,
                    lon: pos.coords.longitude
                })
            });
            const json = await res.json();
            if(json.success) {
                location.reload();
            } else {
                alert("Error: " + json.message);
                if(btn) { btn.disabled = false; btn.textContent = "Start 5-Min Session"; }
            }
        } catch(e) { 
            alert("Network Error"); 
            if(btn) btn.disabled = false;
        }
    }, (err) => {
        alert("Location access denied. As Admin, you MUST enable GPS to set the class location.");
        if(btn) { btn.disabled = false; btn.textContent = "Start 5-Min Session"; }
    }, {enableHighAccuracy: true});
}

async function endSession() {
    if(!confirm("End session now?")) return;
    try {
        await fetch('/api/session/end', {method:'POST'});
        location.reload();
    } catch(e) {
        alert("Network error ending session.");
    }
}

// --- ADMIN MANUAL EDIT LOGIC ---

async function openManualEdit(sessionId) {
    const modal = document.getElementById('manual-modal');
    const list = document.getElementById('student-list');
    
    // Reset and Show Modal
    list.innerHTML = '<div style="padding:20px; text-align:center; color:#888;">Loading student list...</div>';
    document.getElementById('manual-search').value = ''; 
    modal.classList.remove('hidden');
    
    try {
        const res = await fetch(`/api/get_students_for_manual_edit/${sessionId}`);
        const json = await res.json();
        
        if(json.success) {
            list.innerHTML = ''; // Clear loading
            
            if(json.students.length === 0) {
                list.innerHTML = '<div style="padding:20px; text-align:center;">No students found.</div>';
                return;
            }

            json.students.forEach(s => {
                const div = document.createElement('div');
                div.className = 'student-row';
                // HTML for each row
                div.innerHTML = `
                    <div class="s-info">
                        <strong>${s.enrollment_no}</strong>
                        <span>${s.name}</span>
                    </div>
                    <div class="s-action">
                        ${s.is_present 
                            ? '<span class="status-badge present">Present</span>' 
                            : `<button class="btn-sm" onclick="manualMark(${sessionId}, ${s.id}, this)">Mark</button>`
                        }
                    </div>
                `;
                list.appendChild(div);
            });
        }
    } catch(e) { 
        list.innerHTML = '<div style="color:red; padding:20px; text-align:center;">Failed to load data.</div>';
        console.error(e); 
    }
}

async function manualMark(sid, uid, btn) {
    const originalText = btn.textContent;
    btn.textContent = "...";
    btn.disabled = true;
    
    try {
        const res = await fetch('/api/manual_mark_attendance', {
            method:'POST', 
            headers:{'Content-Type':'application/json'}, 
            body:JSON.stringify({session_id:sid, student_id:uid})
        });
        
        if((await res.json()).success) {
            // Replace button with "Present" badge
            const badge = document.createElement("span");
            badge.className = "status-badge present";
            badge.innerText = "Marked";
            btn.replaceWith(badge);
        } else {
            btn.textContent = "Retry";
            btn.disabled = false;
        }
    } catch(e) {
        btn.textContent = "Error";
        btn.disabled = false;
    }
}

function closeModal() { 
    document.getElementById('manual-modal').classList.add('hidden'); 
}

function filterStudents() {
    const term = document.getElementById('manual-search').value.toLowerCase();
    const rows = document.querySelectorAll('.student-row');
    rows.forEach(row => { 
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(term) ? 'flex' : 'none'; 
    });
}

// --- GLOBAL TIMER ---
// Expects 'endTime' variable to be defined in the HTML template
if(typeof endTime !== 'undefined' && endTime) {
    const end = new Date(endTime).getTime();
    
    const interval = setInterval(() => {
        const now = new Date().getTime();
        const diff = end - now;
        
        const el = document.getElementById('timer') || document.getElementById('admin-timer');
        
        if(el) {
            if(diff < 0) { 
                clearInterval(interval);
                el.textContent = "00:00"; 
                // Reload shortly after expire to update UI
                if(diff > -3000) setTimeout(() => location.reload(), 1000);
            } else {
                const m = Math.floor((diff % (1000*60*60))/(1000*60));
                const s = Math.floor((diff % (1000*60))/1000);
                el.textContent = `${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
            }
        }
    }, 1000);
}