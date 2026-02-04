// Utilities
function showMsg(txt, type='error') {
    let el = document.getElementById('status-message');
    if (!el) { el = document.createElement('div'); el.id = 'status-message'; document.body.prepend(el); }
    el.textContent = txt; el.className = `status-message ${type}`; el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 4000);
}

function getDevId() {
    let id = localStorage.getItem('did');
    if(!id) { id = 'dev_' + Math.random().toString(36).substr(2,9) + Date.now().toString(36); localStorage.setItem('did', id); }
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
    const originalText = btn.textContent;
    btn.disabled = true; btn.textContent = "Processing...";
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    data.device_id = getDevId();
    
    try {
        const res = await fetch(`/api/student/${type}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const json = await res.json();
        
        if(json.success) {
            if(type === 'register') { showMsg('Registration Successful!', 'success'); setTimeout(() => location.reload(), 1500); }
            else { window.location.href = '/student/dashboard'; }
        } else {
            showMsg(json.message, 'error');
            btn.disabled = false; btn.textContent = originalText;
        }
    } catch(err) { showMsg("Connection failed.", 'error'); btn.disabled = false; btn.textContent = originalText; }
}

// Student Mark
function mark(sid) {
    const btn = document.getElementById('mark-btn');
    const txt = document.getElementById('gps-status');
    const originalText = btn.textContent;
    btn.disabled = true; btn.textContent = "Locating...";
    
    if(!navigator.geolocation) { showMsg("GPS not supported.", 'error'); btn.disabled = false; return; }
    
    navigator.geolocation.getCurrentPosition(async (pos) => {
        btn.textContent = "Verifying...";
        try {
            const res = await fetch('/api/mark', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({lat: pos.coords.latitude, lon: pos.coords.longitude, session_id: sid})
            });
            const json = await res.json();
            if(json.success) { showMsg("Marked!", 'success'); setTimeout(() => location.reload(), 1500); }
            else { showMsg(json.message, 'error'); btn.disabled = false; btn.textContent = originalText; if(txt) txt.textContent = json.message; }
        } catch(e) { showMsg("Server Error", 'error'); btn.disabled = false; btn.textContent = originalText; }
    }, (err) => { showMsg("Location denied/unavailable.", 'error'); btn.disabled = false; btn.textContent = "Retry"; }, {enableHighAccuracy: true});
}

// Admin Controls
async function startSession() {
    if(!confirm("Start 5 minute session? This sets location to YOUR current spot (80m radius).")) return;
    const btn = document.querySelector('button[onclick="startSession()"]');
    if(btn) { btn.disabled = true; btn.textContent = "Acquiring GPS..."; }

    if (!navigator.geolocation) { alert("GPS not supported."); if(btn) btn.disabled = false; return; }

    navigator.geolocation.getCurrentPosition(async (pos) => {
        try {
            const res = await fetch('/api/session/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({lat: pos.coords.latitude, lon: pos.coords.longitude})
            });
            const json = await res.json();
            if(json.success) location.reload();
            else { alert("Error: " + json.message); if(btn) btn.disabled = false; }
        } catch(e) { alert("Network Error"); if(btn) btn.disabled = false; }
    }, (err) => { alert("Location access denied."); if(btn) btn.disabled = false; }, {enableHighAccuracy: true});
}

async function endSession() {
    if(!confirm("End session?")) return;
    await fetch('/api/session/end', {method:'POST'});
    location.reload();
}

// Admin Manual Edit
async function openManualEdit(sessionId) {
    const modal = document.getElementById('manual-modal');
    const list = document.getElementById('student-list');
    list.innerHTML = '<div style="padding:20px; text-align:center;">Loading...</div>';
    document.getElementById('manual-search').value = ''; 
    modal.classList.remove('hidden');
    
    try {
        const res = await fetch(`/api/get_students_for_manual_edit/${sessionId}`);
        const json = await res.json();
        if(json.success) {
            list.innerHTML = '';
            json.students.forEach(s => {
                const div = document.createElement('div');
                div.className = 'student-row';
                div.innerHTML = `<div class="s-info"><strong>${s.enrollment_no}</strong><span>${s.name}</span></div>
                    <div class="s-action">${s.is_present ? '<span class="status-badge present">Present</span>' : `<button class="btn-sm" onclick="manualMark(${sessionId}, ${s.id}, this)">Mark</button>`}</div>`;
                list.appendChild(div);
            });
        }
    } catch(e) { list.innerHTML = 'Error loading list.'; }
}

async function manualMark(sid, uid, btn) {
    btn.textContent = "...";
    const res = await fetch('/api/manual_mark_attendance', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:sid, student_id:uid})});
    if((await res.json()).success) {
        const badge = document.createElement("span"); badge.className = "status-badge present"; badge.innerText = "Marked";
        btn.replaceWith(badge);
    } else { btn.textContent = "Retry"; }
}

function closeModal() { document.getElementById('manual-modal').classList.add('hidden'); }
function filterStudents() {
    const term = document.getElementById('manual-search').value.toLowerCase();
    document.querySelectorAll('.student-row').forEach(row => { row.style.display = row.innerText.toLowerCase().includes(term) ? 'flex' : 'none'; });
}

// Timer
if(typeof endTime !== 'undefined' && endTime) {
    const end = new Date(endTime).getTime();
    setInterval(() => {
        const diff = end - new Date().getTime();
        const el = document.getElementById('timer') || document.getElementById('admin-timer');
        if(el) {
            if(diff < 0) { el.textContent = "00:00"; if(diff > -3000) setTimeout(() => location.reload(), 1000); }
            else {
                const m = Math.floor((diff % (1000*60*60))/(1000*60));
                const s = Math.floor((diff % (1000*60))/1000);
                el.textContent = `${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
            }
        }
    }, 1000);
}