// Utilities
function showMsg(txt, type='error') {
    const el = document.getElementById('status-message');
    if(el) { 
        el.textContent = txt; 
        el.className = `status-message ${type}`; 
        el.style.display = 'block';
        setTimeout(() => { el.style.display = 'none'; }, 4000);
    }
}

function getDevId() {
    let id = localStorage.getItem('did');
    if(!id) { id = 'dev_' + Math.random().toString(36).substr(2,9); localStorage.setItem('did', id); }
    return id;
}

function toggle() {
    document.getElementById('login-form').classList.toggle('hidden');
    document.getElementById('register-form').classList.toggle('hidden');
}

// Auth
async function auth(e, type) {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    btn.disabled = true; btn.textContent = "Processing...";
    
    const data = Object.fromEntries(new FormData(e.target));
    data.device_id = getDevId();
    
    try {
        const res = await fetch(`/api/student/${type}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const json = await res.json();
        
        if(json.success) {
            if(type === 'register') location.reload();
            else window.location.href = '/student/dashboard';
        } else {
            showMsg(json.message);
            btn.disabled = false; btn.textContent = type === 'login' ? "Secure Login" : "Register Device";
        }
    } catch(err) {
        showMsg("Connection failed");
        btn.disabled = false;
    }
}

// Attendance (Students)
function mark(sid) {
    const btn = document.getElementById('mark-btn');
    const txt = document.getElementById('gps-status');
    btn.disabled = true; btn.textContent = "Locating...";
    
    if(!navigator.geolocation) { alert("GPS not supported"); return; }
    
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
            if(json.success) location.reload();
            else {
                alert(json.message);
                btn.disabled = false; btn.textContent = "Mark Present";
                txt.textContent = json.message;
            }
        } catch(e) { alert("Network Error"); btn.disabled = false; }
    }, (err) => {
        alert("Location access denied.");
        btn.disabled = false;
    }, {enableHighAccuracy: true});
}

// Admin Controls
async function startSession() {
    if(!confirm("Start 5 minute session? This will set the class location to where you are standing NOW.")) return;
    
    const btn = document.querySelector('button[onclick="startSession()"]');
    if(btn) { btn.disabled = true; btn.textContent = "Acquiring GPS..."; }

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
            if(json.success) location.reload();
            else {
                alert("Error: " + json.message);
                if(btn) { btn.disabled = false; btn.textContent = "Start 5-Min Session"; }
            }
        } catch(e) { 
            alert("Network Error"); 
            if(btn) btn.disabled = false;
        }
    }, (err) => {
        alert("Location access denied. You must enable GPS to start the session.");
        if(btn) { btn.disabled = false; btn.textContent = "Start 5-Min Session"; }
    }, {enableHighAccuracy: true});
}

async function endSession() {
    if(!confirm("End session now?")) return;
    await fetch('/api/session/end', {method:'POST'});
    location.reload();
}

// Admin Manual Edit (Live)
async function openManualEdit(sessionId) {
    const modal = document.getElementById('manual-modal');
    const list = document.getElementById('student-list');
    list.innerHTML = '<div style="padding:20px; text-align:center;">Loading...</div>';
    modal.classList.remove('hidden');
    try {
        const res = await fetch(`/api/get_students_for_manual_edit/${sessionId}`);
        const json = await res.json();
        if(json.success) {
            list.innerHTML = '';
            json.students.forEach(s => {
                const div = document.createElement('div');
                div.className = 'student-row';
                div.innerHTML = `<span><strong>${s.enrollment_no}</strong> - ${s.name}</span>
                    ${s.is_present ? '<span class="status-badge present">Present</span>' : `<button class="btn-sm" onclick="manualMark(${sessionId}, ${s.id}, this)">Mark</button>`}`;
                list.appendChild(div);
            });
        }
    } catch(e) { console.error(e); }
}

async function manualMark(sid, uid, btn) {
    btn.textContent = "...";
    const res = await fetch('/api/manual_mark_attendance', {
        method:'POST', 
        headers:{'Content-Type':'application/json'}, 
        body:JSON.stringify({session_id:sid, student_id:uid})
    });
    if((await res.json()).success) {
        const badge = document.createElement("span");
        badge.className = "status-badge present";
        badge.innerText = "Present";
        btn.replaceWith(badge);
    }
}

function closeModal() { document.getElementById('manual-modal').classList.add('hidden'); }

function filterStudents() {
    const term = document.getElementById('manual-search').value.toLowerCase();
    document.querySelectorAll('.student-row').forEach(row => { 
        row.style.display = row.innerText.toLowerCase().includes(term) ? 'flex' : 'none'; 
    });
}

// Timer
if(typeof endTime !== 'undefined' && endTime) {
    const end = new Date(endTime).getTime();
    setInterval(() => {
        const diff = end - new Date().getTime();
        const el = document.getElementById('timer') || document.getElementById('admin-timer');
        if(el) {
            if(diff < 0) { el.textContent = "Ended"; if(diff > -2000) location.reload(); }
            else {
                const m = Math.floor((diff % (1000*60*60))/(1000*60));
                const s = Math.floor((diff % (1000*60))/1000);
                el.textContent = `${m}:${s<10?'0':''}${s}`;
            }
        }
    }, 1000);
}