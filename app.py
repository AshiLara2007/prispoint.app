from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os, json, psutil, shutil, zipfile
from datetime import datetime
from io import BytesIO

app = Flask(__name__)
app.secret_key = "prispoint_v16_final_fixed"

STORAGE_ROOT = 'uploads'
BACKUP_ROOT = 'backups/deleted_files'
USER_FILE = 'users.json'
CHAT_FILE = 'chat_history.json'
LOCK_FILE = 'locks.json'
SECTORS = ['Core_Engine', 'Shaders', 'Assets_3D', 'Scripts', 'Sound_FX']

typing_users = {}

def init_system():
    for d in [STORAGE_ROOT, BACKUP_ROOT] + [os.path.join(STORAGE_ROOT, s) for s in SECTORS]:
        if not os.path.exists(d): os.makedirs(d)
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, 'w') as f: json.dump({"admin": {"pw": "pass123", "quota": 1000}}, f)
    if not os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, 'w') as f: json.dump([], f)
    if not os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, 'w') as f: json.dump({}, f)

def get_db():
    with open(USER_FILE, 'r') as f: return json.load(f)

def get_locks():
    with open(LOCK_FILE, 'r') as f: return json.load(f)

def save_locks(data):
    with open(LOCK_FILE, 'w') as f: json.dump(data, f)

def save_db(data):
    with open(USER_FILE, 'w') as f: json.dump(data, f)

def load_chat():
    if os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, 'r') as f: return json.load(f)
    return []

def save_chat(data):
    with open(CHAT_FILE, 'w') as f: json.dump(data, f)

def get_system_stats():
    total_size, total_files = 0, 0
    for r, d, f in os.walk(STORAGE_ROOT):
        for file in f:
            total_size += os.path.getsize(os.path.join(r, file))
            total_files += 1
    return total_size, total_files

chat_messages = []
init_system()
chat_messages = load_chat()

@app.route('/')
def dashboard():
    if 'user' not in session: return redirect('/login')
    current_s = request.args.get('s', 'Core_Engine')
    db = get_db()
    locks = get_locks()
    u_data = db.get(session['user'], {"quota": 1})
    usage_bytes, total_files = get_system_stats()
    usage_gb = round(usage_bytes / (1024**3), 3)
    files = []
    path = os.path.join(STORAGE_ROOT, current_s)
    if os.path.exists(path):
        for f in os.listdir(path):
            fp = os.path.join(path, f)
            lock_info = locks.get(f"{current_s}/{f}")
            files.append({"name": f, "size": f"{round(os.path.getsize(fp)/1024, 1)} KB", "locked_by": lock_info})
    return render_template('index.html', stats={"usage_gb": usage_gb, "quota_gb": u_data['quota'], "total_files": total_files, "cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent}, files=files, sectors=SECTORS, current=current_s, user=session['user'])

# --- Admin Panel & User Management ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('user') != 'admin': return "Access Denied", 403
    db = get_db()
    if request.method == 'POST':
        act, target = request.form.get('act'), request.form.get('target')
        if act == 'add':
            db[target] = {"pw": request.form.get('pw'), "quota": int(request.form.get('quota'))}
        elif act == 'rem' and target != 'admin':
            db.pop(target, None)
        save_db(db)
        return redirect('/admin')
    
    ulist = [{"name": u, "quota": d.get('quota', 1)} for u, d in db.items()]
    deleted_files = os.listdir(BACKUP_ROOT)
    return render_template('admin.html', users=ulist, deleted_files=deleted_files)

# --- Admin Backup Actions (Download & Delete) ---
@app.route('/admin/download_backup/<filename>')
def download_backup(filename):
    if session.get('user') != 'admin': return "Denied", 403
    path = os.path.join(BACKUP_ROOT, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File Not Found", 404

@app.route('/admin/delete_backup/<filename>')
def delete_backup(filename):
    if session.get('user') != 'admin': return "Denied", 403
    path = os.path.join(BACKUP_ROOT, filename)
    if os.path.exists(path):
        os.remove(path)
    return redirect('/admin')

# --- Regular File Download ---
@app.route('/download/<sector>/<path:filename>')
def download_file(sector, filename):
    if 'user' not in session: return "Unauthorized", 401
    file_path = os.path.join(STORAGE_ROOT, sector, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File Not Found", 404

@app.route('/lock/<sector>/<path:filename>')
def lock_file(sector, filename):
    if 'user' not in session: return "Unauthorized", 401
    locks = get_locks()
    file_key = f"{sector}/{filename}"
    if file_key not in locks:
        locks[file_key] = session['user']
        save_locks(locks)
    return redirect(url_for('dashboard', s=sector))

@app.route('/unlock/<sector>/<path:filename>')
def unlock_file(sector, filename):
    if 'user' not in session: return "Unauthorized", 401
    locks = get_locks()
    file_key = f"{sector}/{filename}"
    if locks.get(file_key) == session['user']:
        locks.pop(file_key, None)
        save_locks(locks)
    return redirect(url_for('dashboard', s=sector))

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session: return "Unauthorized", 401
    sec, file = request.form.get('sector'), request.files.get('file')
    if file:
        locks = get_locks()
        if locks.get(f"{sec}/{file.filename}") and locks.get(f"{sec}/{file.filename}") != session['user']:
            return "FILE_LOCKED", 403
        db = get_db()
        quota_limit = db[session['user']]['quota'] * (1024**3)
        file.seek(0, os.SEEK_END)
        f_size = file.tell()
        file.seek(0)
        u_bytes, _ = get_system_stats()
        if (u_bytes + f_size) > quota_limit: return "QUOTA_FULL", 400
        file.save(os.path.join(STORAGE_ROOT, sec, file.filename))
        return "OK"
    return "Error", 400

@app.route('/delete/<sector>/<path:filename>')
def delete_file(sector, filename):
    if 'user' not in session: return "Unauthorized", 401
    locks = get_locks()
    lock_owner = locks.get(f"{sector}/{filename}")
    if lock_owner and lock_owner != session['user']: return "Locked by another user", 403
    src = os.path.join(STORAGE_ROOT, sector, filename)
    if os.path.exists(src):
        dst = os.path.join(BACKUP_ROOT, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
        shutil.copy2(src, dst)
        os.remove(src)
        if lock_owner:
            locks.pop(f"{sector}/{filename}", None)
            save_locks(locks)
    return redirect(url_for('dashboard', s=sector))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        db = get_db()
        if u in db and db[u]['pw'] == p:
            session['user'] = u
            return redirect('/')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/get_chat_data')
def get_chat_data():
    current_user = session.get('user')
    typers = [u for u, is_typing in typing_users.items() if is_typing and u != current_user]
    return json.dumps({"messages": chat_messages, "typers": typers})

@app.route('/send_message', methods=['POST'])
def send_message():
    user, msg = session.get('user'), request.form.get('msg')
    if user and msg:
        chat_messages.append({"user": user, "msg": msg, "time": datetime.now().strftime('%Y-%m-%d %H:%M')})
        if len(chat_messages) > 500: chat_messages.pop(0)
        save_chat(chat_messages)
        typing_users[user] = False
        return "OK"
    return "Error", 400

@app.route('/update_typing', methods=['POST'])
def update_typing():
    user, status = session.get('user'), request.form.get('status') == 'true'
    if user: typing_users[user] = status
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
