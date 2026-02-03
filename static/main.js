// Utilities
function showMsg(txt, type='error') {
    const el = document.getElementById('msg');
    if(el) { el.textContent = txt; el.className = `message ${type}`; el.style.display = 'block'; }
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

// Attendance
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

// Admin
async function startSession() {
    if(!confirm("Start 5 minute session?")) return;
    navigator.geolocation.getCurrentPosition(async (pos) => {
        await fetch('/api/session/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lat: pos.coords.latitude, lon: pos.coords.longitude})
        });
        location.reload();
    });
}

async function endSession() {
    if(!confirm("End session now?")) return;
    await fetch('/api/session/end', {method:'POST'});
    location.reload();
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