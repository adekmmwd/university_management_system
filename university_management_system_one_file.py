"""
╔══════════════════════════════════════════════════════════════╗
║      UNIVERSITY MANAGEMENT SYSTEM  —  MVP Phase 1            ║
║      CSE342 Agile Software Development — UG2023              ║
║                                                              ║
║  Stack  :  Flask · SQLite · Tailwind CDN (single file)       ║
║  Epics  :  Community · Staff · Curriculum · Facilities       ║
║  Auth   :  Session-based (admin / student / professor / TA)  ║
║                                                              ║
║  Default admin  →  username: admin  |  password: admin123    ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations
import os, sqlite3, threading, webbrowser
from datetime import datetime
from functools import wraps
from typing import Optional, List

from flask import (
    Flask, g, redirect, render_template_string, request,
    session, url_for, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

# ═════════════
#  CONFIG
# ═════════════
APP_NAME   = "UniManage"
BASE_DIR   = os.path.abspath(os.path.dirname(__file__))
DB_PATH    = os.path.join(BASE_DIR, "ums.db")
SECRET_KEY = os.environ.get("UMS_SECRET", "ums-agile-phase1-2026")

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ═════════════
#  DATABASE  
# ═════════════
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        g.db = conn
    return g.db

@app.teardown_appcontext
def close_db(_exc: Optional[BaseException]) -> None:
    conn = g.pop("db", None)
    if conn:
        conn.close()

def q(sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows

def q1(sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    cur = get_db().execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row

def ex(sql: str, params: tuple = ()) -> int:
    cur = get_db().execute(sql, params)
    get_db().commit()
    lid = cur.lastrowid
    cur.close()
    return lid

def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════════
#  SCHEMA — ALL MVP TABLES
# ═══════════════════════════════════════════════════════════════
SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'student',
  full_name     TEXT DEFAULT '',
  email         TEXT DEFAULT '',
  department    TEXT DEFAULT '',
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  student_id  TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  email       TEXT NOT NULL,
  department  TEXT DEFAULT '',
  year        TEXT DEFAULT '',
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_students_sid  ON students(student_id);
CREATE INDEX IF NOT EXISTS idx_students_name ON students(name);

CREATE TABLE IF NOT EXISTS staff (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  staff_id     TEXT UNIQUE NOT NULL,
  name         TEXT NOT NULL,
  role_type    TEXT NOT NULL DEFAULT 'professor',
  email        TEXT DEFAULT '',
  phone        TEXT DEFAULT '',
  office_hours TEXT DEFAULT '',
  department   TEXT DEFAULT '',
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  code        TEXT UNIQUE NOT NULL,
  title       TEXT NOT NULL,
  description TEXT DEFAULT '',
  course_type TEXT NOT NULL DEFAULT 'core',
  department  TEXT DEFAULT '',
  capacity    INTEGER DEFAULT 50,
  status      TEXT NOT NULL DEFAULT 'active',
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  enrolled_at TEXT NOT NULL,
  UNIQUE(student_id, course_id)
);

CREATE TABLE IF NOT EXISTS course_assignments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  staff_id   INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
  course_id  INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  role       TEXT DEFAULT 'professor',
  resp_notes TEXT DEFAULT '',
  UNIQUE(staff_id, course_id)
);

CREATE TABLE IF NOT EXISTS rooms (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  room_number TEXT UNIQUE NOT NULL,
  room_type   TEXT NOT NULL DEFAULT 'classroom',
  capacity    INTEGER DEFAULT 30,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id    INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  staff_id   INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
  title      TEXT NOT NULL,
  date       TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time   TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookings_room_date ON bookings(room_id, date);

CREATE TABLE IF NOT EXISTS announcements (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  title      TEXT NOT NULL,
  body       TEXT NOT NULL,
  created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT NOT NULL,
  description TEXT DEFAULT '',
  event_date  TEXT NOT NULL,
  created_by  INTEGER REFERENCES users(id),
  created_at  TEXT NOT NULL
);
"""

def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    cur = conn.execute("SELECT id FROM users WHERE username='admin'")
    if not cur.fetchone():
        conn.execute(
            "INSERT INTO users(username,password_hash,role,full_name,email,created_at) VALUES(?,?,?,?,?,?)",
            ("admin", generate_password_hash("admin123"), "admin", "System Admin", "admin@ums.edu", now_iso())
        )
        for rn, rt, cap in [("A-101","classroom",40),("A-102","classroom",35),
                             ("B-201","classroom",50),("Lab-1","lab",25),("Lab-2","lab",20)]:
            conn.execute("INSERT OR IGNORE INTO rooms(room_number,room_type,capacity,created_at) VALUES(?,?,?,?)",
                         (rn, rt, cap, now_iso()))
        # Dummy courses
        for code, title, ctype, dept in [
            ("CSE301","Data Structures","core","Computer Science"),
            ("CSE342","Agile Software Dev","core","Computer Science"),
            ("CSE401","Machine Learning","elective","Computer Science"),
            ("EE201","Circuit Analysis","core","Electrical Engineering"),
            ("CSE450","Cloud Computing","elective","Computer Science"),
        ]:
            conn.execute(
                "INSERT OR IGNORE INTO courses(code,title,course_type,department,capacity,status,created_at,updated_at) VALUES(?,?,?,?,50,'active',?,?)",
                (code, title, ctype, dept, now_iso(), now_iso())
            )
        conn.commit()
    conn.close()


# ═══════════════
#  AUTH HELPERS  
# ═══════════════
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                flash("Access denied.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapped
    return decorator

def admin_required(f):
    return login_required(role_required("admin")(f))

def get_current_user():
    uid = session.get("user_id")
    return q1("SELECT * FROM users WHERE id=?", (uid,)) if uid else None


# ═══════════════════════════════════════════════════════════════
#  SHARED HTML — BASE LAYOUT + DESIGN SYSTEM
# ═══════════════════════════════════════════════════════════════
CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
<style>
  :root {
    --navy:    #0f2342;
    --navy2:   #1a3a6b;
    --gold:    #d4952a;
    --gold2:   #f0b840;
    --surface: #f2f4f8;
    --card:    #ffffff;
    --text:    #1a2332;
    --muted:   #64748b;
    --border:  #e2e8f0;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; font-family: 'DM Sans', sans-serif; color: var(--text); background: var(--surface); }
  h1,h2,h3,.serif { font-family: 'Fraunces', Georgia, serif; }

  /* ── Sidebar ── */
  .sidebar {
    width: 248px; min-height: 100vh; background: var(--navy);
    display: flex; flex-direction: column;
    position: sticky; top: 0; height: 100vh; overflow-y: auto; flex-shrink: 0;
  }
  .sidebar-logo { padding: 1.25rem 1.25rem 1rem; border-bottom: 1px solid rgba(255,255,255,.07); }
  .logo-mark { width:38px;height:38px; background:var(--gold); border-radius:10px;
    display:flex;align-items:center;justify-content:center;
    font-family:'Fraunces',serif; color:#fff; font-size:1.1rem; font-weight:700; flex-shrink:0; }
  .logo-name { font-family:'Fraunces',serif; color:#fff; font-size:1rem; line-height:1.2; }
  .logo-sub  { font-size:0.6rem; color:#4a7aaa; font-weight:600; text-transform:uppercase; letter-spacing:.08em; }

  .nav-section { font-size:0.62rem; font-weight:700; text-transform:uppercase; letter-spacing:.1em;
    color:#3a5a7a; padding:.9rem 1.1rem .3rem; }
  .nav-link {
    display:flex; align-items:center; gap:.6rem; padding:.5rem 1.1rem;
    border-radius:.45rem; margin:.1rem .6rem; font-size:.83rem; font-weight:500;
    color:#7aa0c0; text-decoration:none; transition:all .15s;
  }
  .nav-link:hover { background:rgba(255,255,255,.07); color:#fff; }
  .nav-link.active { background:rgba(212,149,42,.18); color:var(--gold2); }
  .nav-link .ic { width:15px; height:15px; flex-shrink:0; }
  .nav-badge { margin-left:auto; background:var(--gold); color:#fff;
    font-size:.62rem; font-weight:800; padding:.1rem .4rem; border-radius:99px; }

  .sidebar-user { padding:.9rem 1.1rem; border-top:1px solid rgba(255,255,255,.07); margin-top:auto; }
  .avatar { width:32px; height:32px; border-radius:50%; background:var(--gold); color:#fff;
    display:flex; align-items:center; justify-content:center; font-weight:700; font-size:.85rem; flex-shrink:0; }

  /* ── Main Layout ── */
  .layout { display:flex; min-height:100vh; }
  .main   { flex:1; display:flex; flex-direction:column; min-width:0; }
  .topbar {
    background:#fff; border-bottom:1px solid var(--border);
    padding:.9rem 2rem; display:flex; align-items:center; justify-content:space-between;
    position:sticky; top:0; z-index:10;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
  }
  .page-title { font-family:'Fraunces',serif; font-size:1.2rem; color:var(--text); }
  .breadcrumb { font-size:.75rem; color:var(--muted); margin-top:.15rem; }
  .content    { flex:1; padding:1.75rem 2rem; }
  .footer { padding:.75rem 2rem; text-align:center; font-size:.72rem; color:#94a3b8; border-top:1px solid var(--border); }

  /* ── Alerts ── */
  .flashes { padding:0 2rem; }
  .alert { border-radius:.55rem; padding:.65rem .9rem; font-size:.83rem; margin-bottom:.6rem;
    display:flex; align-items:center; gap:.5rem; border-left:4px solid transparent; }
  .alert-success { background:#dcfce7; color:#166534; border-color:#22c55e; }
  .alert-danger  { background:#fee2e2; color:#991b1b; border-color:#ef4444; }
  .alert-warning { background:#fef9c3; color:#854d0e; border-color:#eab308; }
  .alert-info    { background:#dbeafe; color:#1e40af; border-color:#3b82f6; }
  .alert-ic { width:15px; height:15px; flex-shrink:0; }

  /* ── Cards ── */
  .card { background:#fff; border-radius:.85rem; box-shadow:0 1px 3px rgba(0,0,0,.05),0 4px 12px rgba(0,0,0,.04); }
  .card-p { padding:1.4rem 1.6rem; }

  /* ── Buttons ── */
  .btn { display:inline-flex; align-items:center; gap:.35rem; border-radius:.5rem;
    font-size:.82rem; font-weight:600; padding:.48rem 1rem; cursor:pointer;
    transition:all .15s; border:none; text-decoration:none; white-space:nowrap; }
  .btn-primary { background:var(--navy); color:#fff; }
  .btn-primary:hover { background:var(--navy2); }
  .btn-gold { background:var(--gold); color:#fff; }
  .btn-gold:hover { background:#b8801e; }
  .btn-outline { background:transparent; color:var(--muted); border:1.5px solid var(--border); }
  .btn-outline:hover { border-color:var(--navy); color:var(--navy); background:#f0f4ff; }
  .btn-danger { background:#fee2e2; color:#991b1b; }
  .btn-danger:hover { background:#fca5a5; }
  .btn-sm { padding:.32rem .75rem; font-size:.76rem; }
  .btn-xs { padding:.22rem .55rem; font-size:.7rem; }

  /* ── Forms ── */
  .form-group { margin-bottom:1rem; }
  .form-label { display:block; font-size:.73rem; font-weight:700; color:var(--muted);
    text-transform:uppercase; letter-spacing:.05em; margin-bottom:.35rem; }
  .form-control {
    width:100%; border:1.5px solid var(--border); border-radius:.5rem;
    padding:.52rem .8rem; font-size:.875rem; font-family:'DM Sans',sans-serif;
    color:var(--text); background:#fff; transition:border .15s;
  }
  .form-control:focus { outline:none; border-color:var(--navy); box-shadow:0 0 0 3px rgba(15,35,66,.08); }
  textarea.form-control { resize:vertical; }

  /* ── Badges ── */
  .badge { display:inline-flex; align-items:center; gap:.25rem;
    padding:.18rem .6rem; border-radius:99px; font-size:.68rem; font-weight:700; }
  .badge-navy   { background:#dbeafe; color:#1e3a5f; }
  .badge-green  { background:#dcfce7; color:#166534; }
  .badge-gold   { background:#fef9c3; color:#854d0e; }
  .badge-red    { background:#fee2e2; color:#991b1b; }
  .badge-gray   { background:#f1f5f9; color:#475569; }
  .badge-purple { background:#f3e8ff; color:#6b21a8; }

  /* ── Table ── */
  .table-wrap { overflow:hidden; border-radius:.85rem; box-shadow:0 1px 3px rgba(0,0,0,.05),0 4px 12px rgba(0,0,0,.04); }
  table.ums-table { width:100%; border-collapse:collapse; background:#fff; }
  .ums-table thead tr { background:var(--navy); }
  .ums-table thead th { padding:.75rem 1.1rem; text-align:left; font-size:.7rem;
    font-weight:700; color:#fff; text-transform:uppercase; letter-spacing:.06em; white-space:nowrap; }
  .ums-table tbody tr { border-bottom:1px solid #f1f5f9; transition:background .1s; }
  .ums-table tbody tr:hover { background:#f8faff; }
  .ums-table tbody td { padding:.7rem 1.1rem; font-size:.85rem; }
  .ums-table tbody tr:last-child { border-bottom:none; }

  /* ── Stat Cards ── */
  .stat-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:1rem; margin-bottom:1.75rem; }
  .stat-card { background:#fff; border-radius:.85rem; padding:1.1rem 1.3rem;
    border:1.5px solid var(--border); display:flex; align-items:center; gap:1rem; }
  .stat-icon { width:42px;height:42px; border-radius:.7rem; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
  .stat-num { font-family:'Fraunces',serif; font-size:1.7rem; color:var(--text); line-height:1; }
  .stat-lbl { font-size:.72rem; color:var(--muted); font-weight:600; margin-top:.2rem; }

  /* ── Misc ── */
  @keyframes fadeUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
  .fade-up { animation:fadeUp .3s ease both; }
  .room-free { background:#f0fdf4; border:1px solid #bbf7d0; border-radius:.6rem; padding:.7rem; text-align:center; }
  .room-busy { background:#fff5f5; border:1px solid #fecaca; border-radius:.6rem; padding:.6rem .8rem; margin-bottom:.4rem; }
  .divider { border:none; border-top:1px solid var(--border); margin:1.2rem 0; }
  .text-muted { color:var(--muted); }
  .empty-state { text-align:center; padding:3.5rem 1rem; }
  .empty-state .ic { opacity:.2; display:block; margin:0 auto .75rem; }
  .section-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:1.25rem; gap:1rem; flex-wrap:wrap; }
  .page-sub { font-size:.78rem; color:var(--muted); margin-top:.1rem; }

  /* ── Login Page ── */
  .login-wrap { min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:var(--navy); background-image:radial-gradient(rgba(255,255,255,.04) 1px, transparent 1px);
    background-size:22px 22px; padding:1rem; }
  .login-card { background:#fff; border-radius:1.25rem; padding:2.5rem;
    box-shadow:0 20px 60px rgba(0,0,0,.35); width:100%; max-width:400px; }
  .login-logo { text-align:center; margin-bottom:2rem; }
  .login-mark { width:54px;height:54px; background:var(--navy); border-radius:14px;
    display:flex;align-items:center;justify-content:center; margin:0 auto .75rem; }
  .login-title { font-family:'Fraunces',serif; font-size:1.6rem; color:var(--text); }
  .login-sub { font-size:.72rem; color:var(--muted); font-weight:600; text-transform:uppercase; letter-spacing:.08em; margin-top:.2rem; }
  .input-icon-wrap { position:relative; }
  .input-icon { position:absolute; left:.75rem; top:50%; transform:translateY(-50%);
    width:15px; height:15px; color:#94a3b8; pointer-events:none; }
  .input-padded { padding-left:2.4rem !important; }
  .demo-box { background:#f8fafc; border:1px solid var(--border); border-radius:.6rem;
    padding:.75rem 1rem; font-size:.78rem; color:var(--muted); margin-top:1.25rem; }
</style>
"""

# ── Master page wrapper ──────────────────────────────────────
def page(title: str, active: str, inner: str, page_title: str = "", breadcrumb: str = "") -> str:
    user = get_current_user()
    if not user:
        return inner  # bare page (login)

    role = session.get("role","")
    ann_count = (q1("SELECT COUNT(*) c FROM announcements") or {"c":0})["c"]
    today_str  = datetime.now().strftime("%A, %d %B %Y")

    def nav(href, icon, label, key, badge=""):
        is_active = "active" if active == key else ""
        b = f'<span class="nav-badge">{badge}</span>' if badge else ""
        return f'<a href="{href}" class="nav-link {is_active}"><i data-lucide="{icon}" class="ic"></i>{label}{b}</a>'

    admin_nav = ""
    if role == "admin":
        admin_nav = f"""
        {nav(url_for('student_new'),   'user-plus',    'Add Student', 'student_new')}
        {nav(url_for('staff_new'),     'user-check',   'Add Staff',   'staff_new')}
        {nav(url_for('course_new'),    'book-plus',    'Add Course',  'course_new')}
        """

    staff_nav = ""
    if role in ("staff","professor","ta","admin"):
        staff_nav = f"""
        {nav(url_for('room_book'),   'calendar-plus',  'Book a Room',  'room_book')}
        {nav(url_for('my_bookings'), 'calendar-check', 'My Bookings',  'bookings')}
        """

    avatar_letter = (user["full_name"] or user["username"] or "?")[0].upper()
    user_display  = user["full_name"] or user["username"]
    ann_badge = str(ann_count) if ann_count else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title} — UniManage</title>
  {CSS}
</head>
<body>
<div class="layout">

<!-- ════ SIDEBAR ════ -->
<aside class="sidebar">
  <div class="sidebar-logo">
    <div style="display:flex;align-items:center;gap:.75rem;">
      <div class="logo-mark">U</div>
      <div>
        <div class="logo-name">UniManage</div>
        <div class="logo-sub">University System</div>
      </div>
    </div>
  </div>

  <nav style="flex:1;padding:.75rem .4rem;">
    <div class="nav-section">Main</div>
    {nav(url_for('dashboard'), 'layout-dashboard', 'Dashboard', 'dashboard')}
    {nav(url_for('profile'),   'user-circle',      'My Profile', 'profile')}

    <div class="nav-section" style="margin-top:.75rem;">Academic</div>
    {nav(url_for('courses_list'), 'book-open',  'Courses',  'courses')}
    {admin_nav}

    <div class="nav-section" style="margin-top:.75rem;">People</div>
    {nav(url_for('students_list'), 'users',     'Students', 'students')}
    {nav(url_for('staff_list'),    'briefcase', 'Staff',    'staff')}

    <div class="nav-section" style="margin-top:.75rem;">Facilities</div>
    {nav(url_for('rooms_list'), 'door-open', 'Room Schedule', 'rooms')}
    {staff_nav}

    <div class="nav-section" style="margin-top:.75rem;">Community</div>
    {nav(url_for('announcements_list'), 'megaphone',     'Announcements',    'announcements', ann_badge)}
    {nav(url_for('events_list'),        'calendar-days', 'Events &amp; Deadlines', 'events')}
  </nav>

  <div class="sidebar-user">
    <div style="display:flex;align-items:center;gap:.65rem;margin-bottom:.6rem;">
      <div class="avatar">{avatar_letter}</div>
      <div style="min-width:0;">
        <div style="color:#fff;font-size:.8rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{user_display}</div>
        <div style="color:#4a7aaa;font-size:.66rem;text-transform:capitalize;">{role}</div>
      </div>
    </div>
    <a href="{url_for('logout')}" class="nav-link" style="color:#f87171;margin:0;">
      <i data-lucide="log-out" class="ic"></i>Sign Out
    </a>
  </div>
</aside>

<!-- ════ MAIN ════ -->
<div class="main">
  <header class="topbar">
    <div>
      <div class="page-title">{page_title or title}</div>
      <div class="breadcrumb">{breadcrumb}</div>
    </div>
    <div style="display:flex;align-items:center;gap:1rem;">
      <span style="font-size:.75rem;color:var(--muted);">{today_str}</span>
      <div class="avatar">{avatar_letter}</div>
    </div>
  </header>

  {"".join(
    f'<div class="flashes"><div class="alert alert-{cat} fade-up">'
    f'<i data-lucide="{"check-circle" if cat=="success" else "alert-circle" if cat=="danger" else "info"}" class="alert-ic"></i>'
    f'{msg}</div></div>'
    for cat, msg in [(c, m) for c, m in __import__("flask").get_flashed_messages(with_categories=True)]
  ) if False else _render_flashes()}

  <main class="content fade-up">
    {inner}
  </main>

  <footer class="footer">
    UniManage · University Management System · Agile Phase 1 MVP · CSE342 (UG2023)
  </footer>
</div>
</div>
<script>
  lucide.createIcons();
  setTimeout(()=>{{
    document.querySelectorAll('.alert').forEach(el=>{{
      el.style.transition='opacity .5s';el.style.opacity='0';
      setTimeout(()=>el.remove(),500);
    }});
  }},4200);
</script>
</body></html>"""
    return html


def _render_flashes() -> str:
    from flask import get_flashed_messages
    msgs = get_flashed_messages(with_categories=True)
    if not msgs:
        return ""
    icons = {"success":"check-circle","danger":"alert-circle","warning":"alert-triangle","info":"info"}
    parts = []
    for cat, msg in msgs:
        ic = icons.get(cat, "info")
        parts.append(
            f'<div class="alert alert-{cat} fade-up">'
            f'<i data-lucide="{ic}" class="alert-ic"></i>{msg}</div>'
        )
    return f'<div class="flashes">{"".join(parts)}</div>'


# ═══════════════════════════════════════════════════════════════
#  LOGIN / LOGOUT
# ═══════════════════════════════════════════════════════════════
LOGIN_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Sign In — UniManage</title>
  {CSS}
  <style>
    @keyframes slideUp{{from{{opacity:0;transform:translateY(18px)}}to{{opacity:1;transform:translateY(0)}}}}
    .slide-up{{animation:slideUp .45s ease both;}}
  </style>
</head>
<body>
<div class="login-wrap">
  <div class="login-card slide-up">
    <div class="login-logo">
      <div class="login-mark">
        <span style="font-family:'Fraunces',serif;color:#fff;font-size:1.5rem;font-weight:700;">U</span>
      </div>
      <div class="login-title">UniManage</div>
      <div class="login-sub">University Management System</div>
    </div>

    {{error_block}}

    <form method="POST" action="/login">
      <div class="form-group">
        <label class="form-label">Username</label>
        <div class="input-icon-wrap">
          <i data-lucide="user" class="input-icon"></i>
          <input type="text" name="username" class="form-control input-padded" placeholder="Enter username" required autofocus>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Password</label>
        <div class="input-icon-wrap">
          <i data-lucide="lock" class="input-icon"></i>
          <input type="password" name="password" class="form-control input-padded" placeholder="Enter password" required>
        </div>
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;padding:.65rem;font-size:.9rem;margin-top:.5rem;">
        Sign In
      </button>
    </form>

    <div class="demo-box">
      <strong style="color:var(--text);">Default Admin</strong><br>
      Username: <code style="font-weight:700;color:var(--navy);">admin</code> &nbsp;
      Password: <code style="font-weight:700;color:var(--navy);">admin123</code>
    </div>

    <p style="text-align:center;font-size:.72rem;color:#94a3b8;margin-top:1.25rem;">
      Faculty of Engineering — Ain Shams University · CSE342
    </p>
  </div>
</div>
<script>lucide.createIcons();</script>
</body></html>"""

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    error_block = ""
    if request.method == "POST":
        uname = request.form.get("username","").strip()
        pwd   = request.form.get("password","")
        user  = q1("SELECT * FROM users WHERE username=?", (uname,))
        if user and check_password_hash(user["password_hash"], pwd):
            session.update({"user_id": user["id"], "role": user["role"],
                            "name": user["full_name"] or user["username"]})
            flash(f"Welcome back, {session['name']}!", "success")
            return redirect(url_for("dashboard"))
        error_block = '<div class="alert alert-danger" style="margin-bottom:1rem;"><i data-lucide="alert-circle" class="alert-ic"></i>Invalid username or password.</div>'
    return render_template_string(LOGIN_HTML.replace("{error_block}", error_block))

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════
@app.route("/dashboard")
@login_required
def dashboard():
    role = session.get("role","")
    uid  = session.get("user_id")
    anns = q("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 6")
    evts = q("SELECT * FROM events WHERE event_date >= date('now') ORDER BY event_date LIMIT 6")

    # Stats
    stat_cards = ""
    def scard(num, label, icon, color):
        return f"""<div class="stat-card">
          <div class="stat-icon" style="background:{color}20;">
            <i data-lucide="{icon}" style="width:20px;height:20px;color:{color};"></i>
          </div>
          <div>
            <div class="stat-num">{num}</div>
            <div class="stat-lbl">{label}</div>
          </div>
        </div>"""

    if role == "admin":
        sc = q1("SELECT COUNT(*) c FROM students")["c"]
        sf = q1("SELECT COUNT(*) c FROM staff")["c"]
        co = q1("SELECT COUNT(*) c FROM courses WHERE status='active'")["c"]
        bk = q1("SELECT COUNT(*) c FROM bookings WHERE date >= date('now')")["c"]
        stat_cards = (scard(sc,"Students","users","#1e3a5f") +
                      scard(sf,"Staff Members","briefcase","#166534") +
                      scard(co,"Active Courses","book-open","#854d0e") +
                      scard(bk,"Upcoming Bookings","calendar-check","#9d174d"))
    elif role == "student":
        st = q1("SELECT id FROM students WHERE user_id=?", (uid,))
        mc = q1("SELECT COUNT(*) c FROM enrollments WHERE student_id=?", (st["id"],))["c"] if st else 0
        oc = q1("SELECT COUNT(*) c FROM courses WHERE status='active'")["c"]
        stat_cards = scard(mc,"My Courses","book-marked","#1e3a5f") + scard(oc,"Open Courses","book-plus","#166534")
    elif role in ("staff","professor","ta"):
        sf = q1("SELECT id FROM staff WHERE user_id=?", (uid,))
        mc = q1("SELECT COUNT(*) c FROM course_assignments WHERE staff_id=?", (sf["id"],))["c"] if sf else 0
        bk = q1("SELECT COUNT(*) c FROM bookings b JOIN staff s ON b.staff_id=s.id WHERE s.user_id=? AND b.date>=date('now')", (uid,))["c"]
        stat_cards = scard(mc,"My Courses","book-open","#1e3a5f") + scard(bk,"Room Bookings","calendar","#9d174d")

    # Announcements column
    def ann_item(a):
        return f"""<div style="background:#f8faff;border:1px solid #e8edf8;border-radius:.6rem;padding:.8rem 1rem;margin-bottom:.6rem;">
          <div style="font-weight:600;font-size:.87rem;color:var(--text);">{a['title']}</div>
          <div style="font-size:.77rem;color:var(--muted);margin-top:.2rem;">{a['body'][:110]}{'…' if len(a['body'])>110 else ''}</div>
          <div style="font-size:.68rem;color:#94a3b8;margin-top:.4rem;">{a['created_at'][:10]}</div>
        </div>"""

    ann_html = "".join(ann_item(a) for a in anns) if anns else \
        '<div class="empty-state" style="padding:2rem;"><i data-lucide="bell-off" style="opacity:.2;display:block;margin:0 auto .5rem;"></i><p style="font-size:.82rem;color:var(--muted);">No announcements yet</p></div>'

    post_btn = f'<a href="{url_for("announcement_new")}" class="btn btn-gold btn-sm" style="margin-top:.75rem;"><i data-lucide="plus" style="width:13px;height:13px;"></i>Post</a>' if role=="admin" else ""

    # Events column
    def evt_item(e):
        mo = e['event_date'][5:7]; dy = e['event_date'][8:10]
        return f"""<div style="display:flex;gap:.75rem;align-items:flex-start;background:#f8faff;border:1px solid #e8edf8;border-radius:.6rem;padding:.8rem;margin-bottom:.6rem;">
          <div style="text-align:center;min-width:38px;background:var(--navy);border-radius:.45rem;padding:.3rem .4rem;">
            <div style="font-size:.65rem;color:#7aa0c0;font-weight:600;">{e['event_date'][:4]}</div>
            <div style="font-size:.85rem;font-weight:700;color:#fff;line-height:1;">{mo}/{dy}</div>
          </div>
          <div>
            <div style="font-weight:600;font-size:.87rem;">{e['title']}</div>
            {f'<div style="font-size:.76rem;color:var(--muted);margin-top:.15rem;">{e["description"][:80]}{"…" if len(e["description"])>80 else ""}</div>' if e['description'] else ''}
          </div>
        </div>"""

    evt_html = "".join(evt_item(e) for e in evts) if evts else \
        '<div class="empty-state" style="padding:2rem;"><i data-lucide="calendar-x" style="opacity:.2;display:block;margin:0 auto .5rem;"></i><p style="font-size:.82rem;color:var(--muted);">No upcoming events</p></div>'

    add_evt_btn = f'<a href="{url_for("event_new")}" class="btn btn-primary btn-sm" style="margin-top:.75rem;"><i data-lucide="plus" style="width:13px;height:13px;"></i>Add Event</a>' if role=="admin" else ""

    # Quick actions
    qa = []
    if role=="admin":
        qa = [("user-plus","btn-gold",url_for('student_new'),"Add Student"),
              ("user-check","btn-primary",url_for('staff_new'),"Add Staff"),
              ("book-plus","btn-gold",url_for('course_new'),"Add Course"),
              ("megaphone","btn-outline",url_for('announcement_new'),"Post Announcement")]
    elif role in ("staff","professor","ta"):
        qa = [("calendar-plus","btn-primary",url_for('room_book'),"Book Room"),
              ("calendar-check","btn-outline",url_for('my_bookings'),"My Bookings"),
              ("book-open","btn-outline",url_for('courses_list'),"View Courses")]
    elif role=="student":
        qa = [("book-open","btn-primary",url_for('courses_list'),"Browse Courses"),
              ("user-circle","btn-outline",url_for('profile'),"My Profile"),
              ("door-open","btn-outline",url_for('rooms_list'),"Room Schedule")]

    qa_html = " ".join(
        f'<a href="{href}" class="btn {cls}"><i data-lucide="{ic}" style="width:14px;height:14px;"></i>{lbl}</a>'
        for ic,cls,href,lbl in qa
    )

    inner = f"""
    <div class="stat-grid">{stat_cards}</div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;margin-bottom:1.25rem;">
      <div class="card card-p">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem;">
          <h3 class="serif" style="font-size:1rem;display:flex;align-items:center;gap:.5rem;">
            <i data-lucide="megaphone" style="width:16px;height:16px;color:var(--gold);"></i>Announcements
          </h3>
          <a href="{url_for('announcements_list')}" style="font-size:.72rem;color:#3b82f6;font-weight:600;">View all</a>
        </div>
        {ann_html}
        {post_btn}
      </div>
      <div class="card card-p">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem;">
          <h3 class="serif" style="font-size:1rem;display:flex;align-items:center;gap:.5rem;">
            <i data-lucide="calendar-days" style="width:16px;height:16px;color:var(--navy);"></i>Upcoming Events
          </h3>
          <a href="{url_for('events_list')}" style="font-size:.72rem;color:#3b82f6;font-weight:600;">View all</a>
        </div>
        {evt_html}
        {add_evt_btn}
      </div>
    </div>

    <div class="card card-p">
      <h3 class="serif" style="font-size:1rem;margin-bottom:.85rem;">Quick Actions</h3>
      <div style="display:flex;flex-wrap:wrap;gap:.6rem;">{qa_html}</div>
    </div>
    """
    return render_template_string(page("Dashboard","dashboard",inner,"Dashboard","Welcome back"))


# ═══════════════════════════════════════════════════════════════
#  STUDENTS  (Community Module — Epic 4)
# ═══════════════════════════════════════════════════════════════
@app.route("/students")
@login_required
def students_list():
    search = request.args.get("search","").strip()
    dept   = request.args.get("dept","").strip()
    year   = request.args.get("year","").strip()
    sql    = "SELECT * FROM students WHERE 1=1"
    params: list = []
    if search:
        sql += " AND (name LIKE ? OR student_id LIKE ?)"; params += [f"%{search}%",f"%{search}%"]
    if dept:
        sql += " AND department=?"; params.append(dept)
    if year:
        sql += " AND year=?"; params.append(year)
    sql += " ORDER BY name"
    students = q(sql, tuple(params))
    depts = [r["department"] for r in q("SELECT DISTINCT department FROM students WHERE department!='' ORDER BY department")]
    years = [r["year"] for r in q("SELECT DISTINCT year FROM students WHERE year!='' ORDER BY year")]
    role = session.get("role","")

    rows = ""
    for s in students:
        av = s["name"][0].upper()
        edit_del = ""
        if role == "admin":
            edit_del = f"""
              <a href="{url_for('student_edit', sid=s['id'])}" class="btn btn-outline btn-xs">
                <i data-lucide="pencil" style="width:11px;height:11px;"></i>Edit</a>
              <form method="POST" action="{url_for('student_delete', sid=s['id'])}" style="display:inline;"
                    onsubmit="return confirm('Delete {s['name']}?')">
                <button class="btn btn-danger btn-xs">
                  <i data-lucide="trash-2" style="width:11px;height:11px;"></i>Delete</button>
              </form>"""
        rows += f"""<tr>
          <td><span class="badge badge-navy">{s['student_id']}</span></td>
          <td>
            <div style="display:flex;align-items:center;gap:.55rem;">
              <div style="width:28px;height:28px;background:var(--navy);color:#fff;border-radius:50%;
                display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;flex-shrink:0;">{av}</div>
              <span style="font-weight:500;">{s['name']}</span>
            </div>
          </td>
          <td style="color:var(--muted);">{s['email']}</td>
          <td>{'<span class="badge badge-gray">'+s['department']+'</span>' if s['department'] else '<span style="color:#94a3b8;">—</span>'}</td>
          <td>{'Year '+s['year'] if s['year'] else '<span style="color:#94a3b8;">—</span>'}</td>
          <td><div style="display:flex;gap:.4rem;justify-content:flex-end;">{edit_del}</div></td>
        </tr>"""

    if not students:
        rows = f"""<tr><td colspan="6" class="empty-state">
          <i data-lucide="users" style="width:34px;height:34px;" class="ic"></i>
          <p style="font-size:.85rem;color:var(--muted);">No students found{' for "'+search+'"' if search else ''}.</p>
          {'<a href="'+url_for("student_new")+'" class="btn btn-gold" style="margin-top:.75rem;">Add First Student</a>' if role=='admin' else ''}
        </td></tr>"""

    dept_opts = "".join(f'<option value="{d}" {"selected" if dept==d else ""}>{d}</option>' for d in depts)
    year_opts = "".join(f'<option value="{y}" {"selected" if year==y else ""}>Year {y}</option>' for y in years)
    add_btn = f'<a href="{url_for("student_new")}" class="btn btn-gold"><i data-lucide="user-plus" style="width:14px;height:14px;"></i>Add Student</a>' if role=="admin" else ""
    clear = f'<a href="{url_for("students_list")}" class="btn btn-outline btn-sm">Clear</a>' if (search or dept or year) else ""

    inner = f"""
    <div class="section-header">
      <form method="GET" style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;">
        <div style="position:relative;">
          <i data-lucide="search" style="position:absolute;left:.6rem;top:50%;transform:translateY(-50%);width:13px;height:13px;color:#94a3b8;"></i>
          <input type="text" name="search" value="{search}" placeholder="Search name or ID…"
                 class="form-control" style="padding-left:2.1rem;width:210px;">
        </div>
        <select name="dept" class="form-control" style="width:180px;">
          <option value="">All Departments</option>{dept_opts}
        </select>
        <select name="year" class="form-control" style="width:120px;">
          <option value="">All Years</option>{year_opts}
        </select>
        <button class="btn btn-primary btn-sm"><i data-lucide="filter" style="width:13px;height:13px;"></i>Filter</button>
        {clear}
      </form>
      {add_btn}
    </div>
    <div class="table-wrap">
      <table class="ums-table">
        <thead><tr>
          <th>Student ID</th><th>Name</th><th>Email</th><th>Department</th><th>Year</th>
          <th style="text-align:right;">Actions</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p style="font-size:.73rem;color:var(--muted);margin-top:.6rem;">{len(students)} student(s)</p>
    """
    return render_template_string(page("Students","students",inner,"Student Records","Community Module · Student Management"))


@app.route("/students/new", methods=["GET","POST"])
@admin_required
def student_new():
    if request.method == "POST":
        sid   = request.form.get("student_id","").strip()
        name  = request.form.get("name","").strip()
        email = request.form.get("email","").strip()
        dept  = request.form.get("department","").strip()
        year  = request.form.get("year","").strip()
        if not sid or not name or not email:
            flash("Student ID, Name, and Email are required.", "danger")
        elif "@" not in email:
            flash("Invalid email address.", "danger")
        elif q1("SELECT id FROM students WHERE student_id=?", (sid,)):
            flash("Student ID already exists.", "danger")
        else:
            ts    = now_iso()
            uname = sid.lower()
            ex("INSERT OR IGNORE INTO users(username,password_hash,role,full_name,email,department,created_at) VALUES(?,?,?,?,?,?,?)",
               (uname, generate_password_hash(sid), "student", name, email, dept, ts))
            u = q1("SELECT id FROM users WHERE username=?", (uname,))
            ex("INSERT INTO students(user_id,student_id,name,email,department,year,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
               (u["id"] if u else None, sid, name, email, dept, year, ts, ts))
            flash(f"Student {name} created! Login: {uname} / {sid}", "success")
            return redirect(url_for("students_list"))
    return render_template_string(page("Add Student","student_new",_student_form(),"Add New Student","Students · New"))


@app.route("/students/<int:sid>/edit", methods=["GET","POST"])
@admin_required
def student_edit(sid):
    s = q1("SELECT * FROM students WHERE id=?", (sid,))
    if not s: abort(404)
    if request.method == "POST":
        name  = request.form.get("name","").strip()
        email = request.form.get("email","").strip()
        dept  = request.form.get("department","").strip()
        year  = request.form.get("year","").strip()
        ts = now_iso()
        ex("UPDATE students SET name=?,email=?,department=?,year=?,updated_at=? WHERE id=?",
           (name,email,dept,year,ts,sid))
        if s["user_id"]:
            ex("UPDATE users SET full_name=?,email=?,department=? WHERE id=?", (name,email,dept,s["user_id"]))
        flash("Student updated.", "success")
        return redirect(url_for("students_list"))
    return render_template_string(page("Edit Student","student_new",_student_form(s),"Edit Student","Students · Edit"))


@app.route("/students/<int:sid>/delete", methods=["POST"])
@admin_required
def student_delete(sid):
    ex("DELETE FROM students WHERE id=?", (sid,))
    flash("Student record deleted.", "success")
    return redirect(url_for("students_list"))


def _student_form(s=None):
    DEPTS = ["Computer Science","Computer Engineering","Electrical Engineering",
             "Mechanical Engineering","Civil Engineering","Information Systems"]
    dept_opts = "".join(f'<option value="{d}" {"selected" if s and s["department"]==d else ""}>{d}</option>' for d in DEPTS)
    year_opts = "".join(f'<option value="{y}" {"selected" if s and s["year"]==y else ""}>Year {y}</option>' for y in "12345")
    sid_field = "" if s else """
      <div class="form-group">
        <label class="form-label">Student ID *</label>
        <input type="text" name="student_id" required class="form-control" placeholder="e.g. 23P0328" maxlength="20">
        <div style="font-size:.72rem;color:var(--muted);margin-top:.3rem;">Must be unique. Also used as initial login password.</div>
      </div>"""
    return f"""
    <div style="max-width:520px;">
      <div class="card card-p">
        <form method="POST">
          {sid_field}
          <div class="form-group">
            <label class="form-label">Full Name *</label>
            <input type="text" name="name" required class="form-control" value="{s['name'] if s else ''}" placeholder="Full name">
          </div>
          <div class="form-group">
            <label class="form-label">University Email *</label>
            <input type="email" name="email" required class="form-control" value="{s['email'] if s else ''}" placeholder="student@university.edu">
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
            <div class="form-group">
              <label class="form-label">Department</label>
              <select name="department" class="form-control">
                <option value="">— Select —</option>{dept_opts}
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Year</label>
              <select name="year" class="form-control">
                <option value="">— Select —</option>{year_opts}
              </select>
            </div>
          </div>
          <hr class="divider">
          <div style="display:flex;gap:.6rem;">
            <button class="btn btn-gold">
              <i data-lucide="{'save' if s else 'user-plus'}" style="width:14px;height:14px;"></i>
              {'Save Changes' if s else 'Create Student'}
            </button>
            <a href="{url_for('students_list')}" class="btn btn-outline">Cancel</a>
          </div>
        </form>
      </div>
    </div>"""


# ═══════════════════════════════════════════════════════════════
#  STAFF  (Staff Module — Epic 3)
# ═══════════════════════════════════════════════════════════════
@app.route("/staff")
@login_required
def staff_list():
    rf   = request.args.get("role_type","").strip()
    sql  = "SELECT * FROM staff WHERE 1=1"
    params: list = []
    if rf:
        sql += " AND role_type=?"; params.append(rf)
    sql += " ORDER BY name"
    staff = q(sql, tuple(params))
    role  = session.get("role","")

    cards = ""
    for s in staff:
        badge = '<span class="badge badge-navy">Professor</span>' if s["role_type"]=="professor" else '<span class="badge badge-gold">Teaching Assistant</span>'
        info  = "".join(
            f'<div style="display:flex;align-items:center;gap:.4rem;font-size:.76rem;color:var(--muted);margin-top:.2rem;">'
            f'<i data-lucide="{ic}" style="width:11px;height:11px;"></i>{val}</div>'
            for ic, val in [("building",s["department"]),("mail",s["email"]),("clock",s["office_hours"])]
            if val
        )
        edit_btn = f'<a href="{url_for("staff_edit", sid=s["id"])}" class="btn btn-outline btn-xs"><i data-lucide="pencil" style="width:11px;height:11px;"></i>Edit</a>' if role=="admin" else ""
        cards += f"""
        <div class="card card-p" style="display:flex;flex-direction:column;">
          <div style="display:flex;gap:.75rem;align-items:flex-start;margin-bottom:.75rem;">
            <div style="width:42px;height:42px;background:{'var(--navy)' if s['role_type']=='professor' else '#854d0e'};
              color:#fff;border-radius:.6rem;display:flex;align-items:center;justify-content:center;
              font-size:1.1rem;font-weight:700;flex-shrink:0;">{s['name'][0].upper()}</div>
            <div style="flex:1;min-width:0;">
              <div style="font-weight:600;font-size:.9rem;color:var(--text);">{s['name']}</div>
              <div style="display:flex;gap:.35rem;margin-top:.3rem;flex-wrap:wrap;">{badge}<span class="badge badge-gray">{s['staff_id']}</span></div>
            </div>
          </div>
          {info}
          <div style="display:flex;gap:.4rem;margin-top:.85rem;padding-top:.75rem;border-top:1px solid var(--border);">
            <a href="{url_for('staff_courses', sid=s['id'])}" class="btn btn-outline btn-xs">
              <i data-lucide="book-open" style="width:11px;height:11px;"></i>Courses</a>
            {edit_btn}
          </div>
        </div>"""

    if not cards:
        cards = f"""<div class="card card-p" style="grid-column:1/-1;" >
          <div class="empty-state"><i data-lucide="briefcase" style="width:34px;height:34px;" class="ic"></i>
          <p style="font-size:.85rem;color:var(--muted);">No staff members found.</p>
          {'<a href="'+url_for("staff_new")+'" class="btn btn-gold" style="margin-top:.75rem;">Add First Staff</a>' if role=='admin' else ''}
          </div></div>"""

    add_btn = f'<a href="{url_for("staff_new")}" class="btn btn-gold"><i data-lucide="user-check" style="width:14px;height:14px;"></i>Add Staff</a>' if role=="admin" else ""
    rf_sel  = lambda v,lbl: f'<option value="{v}" {"selected" if rf==v else ""}>{lbl}</option>'

    inner = f"""
    <div class="section-header">
      <form method="GET" style="display:flex;gap:.5rem;">
        <select name="role_type" class="form-control" style="width:170px;" onchange="this.form.submit()">
          <option value="">All Roles</option>
          {rf_sel('professor','Professors')}{rf_sel('ta','Teaching Assistants')}
        </select>
        {'<a href="'+url_for("staff_list")+'" class="btn btn-outline btn-sm">Clear</a>' if rf else ''}
      </form>
      {add_btn}
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:1rem;">
      {cards}
    </div>"""
    return render_template_string(page("Staff","staff",inner,"Staff Directory","Staff Module · Professors & TAs"))


@app.route("/staff/new", methods=["GET","POST"])
@admin_required
def staff_new():
    if request.method == "POST":
        sid   = request.form.get("staff_id","").strip()
        name  = request.form.get("name","").strip()
        rt    = request.form.get("role_type","professor")
        email = request.form.get("email","").strip()
        phone = request.form.get("phone","").strip()
        oh    = request.form.get("office_hours","").strip()
        dept  = request.form.get("department","").strip()
        if not sid or not name:
            flash("Staff ID and Name are required.", "danger")
        elif q1("SELECT id FROM staff WHERE staff_id=?", (sid,)):
            flash("Staff ID already exists.", "danger")
        else:
            ts = now_iso()
            uname = sid.lower()
            ex("INSERT OR IGNORE INTO users(username,password_hash,role,full_name,email,department,created_at) VALUES(?,?,?,?,?,?,?)",
               (uname, generate_password_hash(sid), rt, name, email, dept, ts))
            u = q1("SELECT id FROM users WHERE username=?", (uname,))
            ex("INSERT INTO staff(user_id,staff_id,name,role_type,email,phone,office_hours,department,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (u["id"] if u else None, sid, name, rt, email, phone, oh, dept, ts, ts))
            flash(f"Staff member {name} created.", "success")
            return redirect(url_for("staff_list"))
    return render_template_string(page("Add Staff","staff_new",_staff_form(),"Add Staff Member","Staff · New"))


@app.route("/staff/<int:sid>/edit", methods=["GET","POST"])
@admin_required
def staff_edit(sid):
    s = q1("SELECT * FROM staff WHERE id=?", (sid,))
    if not s: abort(404)
    if request.method == "POST":
        name  = request.form.get("name","").strip()
        rt    = request.form.get("role_type", s["role_type"])
        email = request.form.get("email","").strip()
        phone = request.form.get("phone","").strip()
        oh    = request.form.get("office_hours","").strip()
        dept  = request.form.get("department","").strip()
        ts    = now_iso()
        ex("UPDATE staff SET name=?,role_type=?,email=?,phone=?,office_hours=?,department=?,updated_at=? WHERE id=?",
           (name,rt,email,phone,oh,dept,ts,sid))
        if s["user_id"]:
            ex("UPDATE users SET full_name=?,role=?,email=?,department=? WHERE id=?", (name,rt,email,dept,s["user_id"]))
        flash("Staff updated.", "success")
        return redirect(url_for("staff_list"))
    return render_template_string(page("Edit Staff","staff",_staff_form(s),"Edit Staff Member","Staff · Edit"))


@app.route("/staff/<int:sid>/courses")
@login_required
def staff_courses(sid):
    s  = q1("SELECT * FROM staff WHERE id=?", (sid,))
    if not s: abort(404)
    me = q1("SELECT id FROM staff WHERE user_id=?", (session["user_id"],))
    if session["role"] != "admin" and (not me or me["id"] != sid):
        flash("Access denied.", "danger"); return redirect(url_for("dashboard"))
    courses = q("""SELECT c.*,ca.id ca_id,ca.role assigned_role,ca.resp_notes
        FROM course_assignments ca JOIN courses c ON c.id=ca.course_id
        WHERE ca.staff_id=? ORDER BY c.code""", (sid,))
    uid = session.get("user_id","")
    rows = ""
    for c in courses:
        ct_badge = '<span class="badge badge-green">Core</span>' if c["course_type"]=="core" else '<span class="badge badge-gold">Elective</span>'
        can_edit = session["role"]=="admin" or (me and me["id"]==sid)
        resp_form = f"""
          <form method="POST" action="{url_for('staff_update_resp', sid=sid, caid=c['ca_id'])}"
                style="display:flex;gap:.4rem;margin-top:.5rem;">
            <input type="text" name="resp_notes" value="{c['resp_notes'] or ''}"
                   class="form-control" style="flex:1;font-size:.8rem;"
                   placeholder="Describe responsibilities…">
            <button class="btn btn-primary btn-xs">
              <i data-lucide="save" style="width:11px;height:11px;"></i>Save</button>
          </form>""" if can_edit else ""
        rows += f"""
        <div class="card card-p" style="margin-bottom:.75rem;">
          <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.4rem;">
            <span style="font-family:monospace;font-weight:700;color:var(--navy);font-size:.9rem;">{c['code']}</span>
            {ct_badge}<span class="badge badge-purple">{c['assigned_role'].title()}</span>
          </div>
          <div style="font-weight:600;">{c['title']}</div>
          {f'<div style="font-size:.76rem;color:var(--muted);">{c["department"]}</div>' if c['department'] else ''}
          <div style="margin-top:.65rem;padding-top:.65rem;border-top:1px solid var(--border);">
            <div style="font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:.35rem;">Responsibilities</div>
            {f'<p style="font-size:.83rem;">{c["resp_notes"]}</p>' if c['resp_notes'] else '<p style="font-size:.82rem;color:#94a3b8;font-style:italic;">Not set.</p>'}
            {resp_form}
          </div>
        </div>"""

    if not courses:
        rows = '<div class="empty-state"><i data-lucide="book-open" style="width:32px;height:32px;" class="ic"></i><p style="font-size:.85rem;color:var(--muted);">No courses assigned.</p></div>'

    badge = '<span class="badge badge-navy">Professor</span>' if s["role_type"]=="professor" else '<span class="badge badge-gold">TA</span>'
    inner = f"""
    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;">
      <div style="width:48px;height:48px;background:var(--navy);color:#fff;border-radius:.7rem;
        display:flex;align-items:center;justify-content:center;font-size:1.2rem;font-weight:700;">{s['name'][0].upper()}</div>
      <div>
        <h2 class="serif" style="font-size:1.2rem;">{s['name']}</h2>
        <div style="display:flex;gap:.35rem;margin-top:.2rem;">{badge}<span class="badge badge-gray">{s['staff_id']}</span></div>
      </div>
    </div>
    {rows}
    <a href="{url_for('staff_list')}" class="btn btn-outline" style="margin-top:.5rem;">
      <i data-lucide="arrow-left" style="width:13px;height:13px;"></i>Back to Staff</a>"""
    return render_template_string(page(f"{s['name']} — Courses","staff",inner,"Assigned Courses",f"Staff · {s['name']}"))


@app.route("/staff/<int:sid>/courses/<int:caid>/resp", methods=["POST"])
@login_required
def staff_update_resp(sid, caid):
    me = q1("SELECT id FROM staff WHERE user_id=?", (session["user_id"],))
    if session["role"] != "admin" and (not me or me["id"] != sid):
        flash("Access denied.", "danger"); return redirect(url_for("dashboard"))
    ex("UPDATE course_assignments SET resp_notes=? WHERE id=? AND staff_id=?",
       (request.form.get("resp_notes","").strip(), caid, sid))
    flash("Responsibilities saved.", "success")
    return redirect(url_for("staff_courses", sid=sid))


def _staff_form(s=None):
    DEPTS = ["Computer Science","Computer Engineering","Electrical Engineering",
             "Mechanical Engineering","Civil Engineering","Information Systems"]
    dept_opts = "".join(f'<option value="{d}" {"selected" if s and s["department"]==d else ""}>{d}</option>' for d in DEPTS)
    sid_field = "" if s else """
      <div class="form-group">
        <label class="form-label">Staff ID *</label>
        <input type="text" name="staff_id" required class="form-control" placeholder="e.g. PROF001">
        <div style="font-size:.72rem;color:var(--muted);margin-top:.3rem;">Also used as initial login password.</div>
      </div>"""
    def sel(val, lbl):
        return f'<option value="{val}" {"selected" if s and s["role_type"]==val else ""}>{lbl}</option>'
    return f"""
    <div style="max-width:520px;"><div class="card card-p">
      <form method="POST">
        {sid_field}
        <div class="form-group">
          <label class="form-label">Full Name *</label>
          <input type="text" name="name" required class="form-control" value="{s['name'] if s else ''}" placeholder="Full name">
        </div>
        <div class="form-group">
          <label class="form-label">Role *</label>
          <select name="role_type" class="form-control">
            {sel('professor','Professor')}{sel('ta','Teaching Assistant (TA)')}
          </select>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
          <div class="form-group">
            <label class="form-label">Email</label>
            <input type="email" name="email" class="form-control" value="{s['email'] if s else ''}" placeholder="staff@university.edu">
          </div>
          <div class="form-group">
            <label class="form-label">Phone</label>
            <input type="text" name="phone" class="form-control" value="{s['phone'] if s else ''}" placeholder="+20 …">
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Office Hours</label>
          <input type="text" name="office_hours" class="form-control" value="{s['office_hours'] if s else ''}" placeholder="e.g. Sun–Tue 10am–12pm">
        </div>
        <div class="form-group">
          <label class="form-label">Department</label>
          <select name="department" class="form-control">
            <option value="">— Select —</option>{dept_opts}
          </select>
        </div>
        <hr class="divider">
        <div style="display:flex;gap:.6rem;">
          <button class="btn btn-gold">
            <i data-lucide="{'save' if s else 'user-check'}" style="width:14px;height:14px;"></i>
            {'Save Changes' if s else 'Create Staff Member'}
          </button>
          <a href="{url_for('staff_list')}" class="btn btn-outline">Cancel</a>
        </div>
      </form>
    </div></div>"""


# ═══════════════════════════════════════════════════════════════
#  COURSES  (Curriculum Module — Epic 2)
# ═══════════════════════════════════════════════════════════════
@app.route("/courses")
@login_required
def courses_list():
    role  = session.get("role","")
    uid   = session.get("user_id")
    ctype = request.args.get("type","").strip()
    dept  = request.args.get("dept","").strip()
    sql   = "SELECT * FROM courses WHERE status='active'"
    params: list = []
    if ctype:
        sql += " AND course_type=?"; params.append(ctype)
    if dept:
        sql += " AND department=?"; params.append(dept)
    sql += " ORDER BY code"
    courses = q(sql, tuple(params))
    depts   = [r["department"] for r in q("SELECT DISTINCT department FROM courses WHERE department!='' ORDER BY department")]

    enrolled_ids: set = set()
    if role == "student":
        st = q1("SELECT id FROM students WHERE user_id=?", (uid,))
        if st:
            enrolled_ids = {r["course_id"] for r in q("SELECT course_id FROM enrollments WHERE student_id=?", (st["id"],))}

    cards = ""
    for c in courses:
        enrolled_count = (q1("SELECT COUNT(*) c FROM enrollments WHERE course_id=?", (c["id"],)) or {"c":0})["c"]
        ct_badge = '<span class="badge badge-green">Core</span>' if c["course_type"]=="core" else '<span class="badge badge-gold">Elective</span>'
        cap_color = "#166534" if enrolled_count < c["capacity"] else "#991b1b"
        actions = ""
        if role == "student":
            if c["id"] in enrolled_ids:
                actions = '<span class="badge badge-green" style="padding:.35rem .7rem;"><i data-lucide="check-circle" style="width:12px;height:12px;"></i>Enrolled</span>'
            elif enrolled_count >= c["capacity"]:
                actions = '<span class="badge badge-red" style="padding:.35rem .7rem;">Full</span>'
            else:
                actions = f'<form method="POST" action="{url_for("course_enroll",cid=c["id"])}"><button class="btn btn-primary btn-sm"><i data-lucide="plus-circle" style="width:12px;height:12px;"></i>Enroll</button></form>'
        if role in ("admin","coordinator"):
            actions = f"""
              <a href="{url_for('course_edit',cid=c['id'])}" class="btn btn-outline btn-xs">
                <i data-lucide="pencil" style="width:11px;height:11px;"></i>Edit</a>
              <a href="{url_for('course_assign',cid=c['id'])}" class="btn btn-outline btn-xs">
                <i data-lucide="user-check" style="width:11px;height:11px;"></i>Staff</a>
              <form method="POST" action="{url_for('course_deactivate',cid=c['id'])}" style="display:inline;"
                    onsubmit="return confirm('Deactivate {c['code']}?')">
                <button class="btn btn-danger btn-xs"><i data-lucide="eye-off" style="width:11px;height:11px;"></i>Remove</button>
              </form>"""

        cards += f"""
        <div class="card card-p" style="display:flex;flex-direction:column;">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:.5rem;margin-bottom:.6rem;">
            <div>
              <span style="font-family:monospace;font-weight:700;color:var(--navy);font-size:.9rem;">{c['code']}</span>
              <div style="display:flex;gap:.3rem;margin-top:.3rem;flex-wrap:wrap;">{ct_badge}
                {'<span class="badge badge-gray">'+c['department']+'</span>' if c['department'] else ''}
              </div>
            </div>
          </div>
          <h4 style="font-weight:600;font-size:.92rem;margin-bottom:.4rem;">{c['title']}</h4>
          {f'<p style="font-size:.78rem;color:var(--muted);margin-bottom:.5rem;">{c["description"][:100]}{"…" if len(c["description"])>100 else ""}</p>' if c['description'] else ''}
          <div style="font-size:.75rem;color:{cap_color};font-weight:600;margin-bottom:.75rem;">
            <i data-lucide="users" style="width:11px;height:11px;vertical-align:middle;"></i>
            {enrolled_count}/{c['capacity']} enrolled
          </div>
          <div style="margin-top:auto;display:flex;gap:.4rem;flex-wrap:wrap;">{actions}</div>
        </div>"""

    if not cards:
        cards = f"""<div class="card card-p" style="grid-column:1/-1;">
          <div class="empty-state"><i data-lucide="book-x" style="width:34px;height:34px;" class="ic"></i>
          <p style="font-size:.85rem;color:var(--muted);">No courses found.</p>
          {'<a href="'+url_for("course_new")+'" class="btn btn-gold" style="margin-top:.75rem;">Add First Course</a>' if role in ("admin","coordinator") else ''}
          </div></div>"""

    dept_opts = "".join(f'<option value="{d}" {"selected" if dept==d else ""}>{d}</option>' for d in depts)
    add_btn = f'<a href="{url_for("course_new")}" class="btn btn-gold"><i data-lucide="book-plus" style="width:14px;height:14px;"></i>Add Course</a>' if role in ("admin","coordinator") else ""
    type_sel = lambda v, lbl: f'<option value="{v}" {"selected" if ctype==v else ""}>{lbl}</option>'
    clear = f'<a href="{url_for("courses_list")}" class="btn btn-outline btn-sm">Clear</a>' if (ctype or dept) else ""

    inner = f"""
    <div class="section-header">
      <form method="GET" style="display:flex;gap:.5rem;flex-wrap:wrap;">
        <select name="type" class="form-control" style="width:130px;" onchange="this.form.submit()">
          <option value="">All Types</option>{type_sel('core','Core')}{type_sel('elective','Elective')}
        </select>
        <select name="dept" class="form-control" style="width:200px;" onchange="this.form.submit()">
          <option value="">All Departments</option>{dept_opts}
        </select>
        {clear}
      </form>
      {add_btn}
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(265px,1fr));gap:1rem;">
      {cards}
    </div>"""
    return render_template_string(page("Courses","courses",inner,"Course Catalog","Curriculum Module · Core & Elective Subjects"))


@app.route("/courses/new", methods=["GET","POST"])
@login_required
@role_required("admin","coordinator")
def course_new():
    if request.method == "POST":
        code  = request.form.get("code","").strip().upper()
        title = request.form.get("title","").strip()
        desc  = request.form.get("description","").strip()
        ctype = request.form.get("course_type","core")
        dept  = request.form.get("department","").strip()
        cap   = int(request.form.get("capacity",50) or 50)
        if not code or not title:
            flash("Code and Title required.", "danger")
        elif q1("SELECT id FROM courses WHERE code=?", (code,)):
            flash("Course code already exists.", "danger")
        else:
            ts = now_iso()
            ex("INSERT INTO courses(code,title,description,course_type,department,capacity,status,created_at,updated_at) VALUES(?,?,?,?,?,?,'active',?,?)",
               (code,title,desc,ctype,dept,cap,ts,ts))
            flash(f"Course {code} added.", "success")
            return redirect(url_for("courses_list"))
    return render_template_string(page("Add Course","course_new",_course_form(),"Add New Course","Courses · New"))


@app.route("/courses/<int:cid>/edit", methods=["GET","POST"])
@login_required
@role_required("admin","coordinator")
def course_edit(cid):
    c = q1("SELECT * FROM courses WHERE id=?", (cid,))
    if not c: abort(404)
    if request.method == "POST":
        title = request.form.get("title","").strip()
        desc  = request.form.get("description","").strip()
        ctype = request.form.get("course_type", c["course_type"])
        dept  = request.form.get("department","").strip()
        cap   = int(request.form.get("capacity", c["capacity"]) or 50)
        ex("UPDATE courses SET title=?,description=?,course_type=?,department=?,capacity=?,updated_at=? WHERE id=?",
           (title,desc,ctype,dept,cap,now_iso(),cid))
        flash("Course updated.", "success")
        return redirect(url_for("courses_list"))
    return render_template_string(page("Edit Course","courses",_course_form(c),"Edit Course","Courses · Edit"))


@app.route("/courses/<int:cid>/deactivate", methods=["POST"])
@login_required
@role_required("admin","coordinator")
def course_deactivate(cid):
    if (q1("SELECT COUNT(*) c FROM enrollments WHERE course_id=?", (cid,)) or {"c":0})["c"] > 0:
        flash("Cannot remove course with active enrollments.", "danger")
    else:
        ex("UPDATE courses SET status='inactive' WHERE id=?", (cid,))
        flash("Course marked inactive.", "success")
    return redirect(url_for("courses_list"))


@app.route("/courses/<int:cid>/enroll", methods=["POST"])
@login_required
def course_enroll(cid):
    if session.get("role") != "student":
        flash("Only students can enroll.", "danger"); return redirect(url_for("courses_list"))
    uid = session.get("user_id")
    st  = q1("SELECT * FROM students WHERE user_id=?", (uid,))
    if not st:
        flash("Student profile not found.", "danger"); return redirect(url_for("courses_list"))
    c   = q1("SELECT * FROM courses WHERE id=? AND status='active'", (cid,))
    if not c:
        flash("Course not available.", "danger"); return redirect(url_for("courses_list"))
    if (q1("SELECT COUNT(*) c FROM enrollments WHERE course_id=?", (cid,)) or {"c":0})["c"] >= c["capacity"]:
        flash("Course is full.", "danger"); return redirect(url_for("courses_list"))
    if q1("SELECT id FROM enrollments WHERE student_id=? AND course_id=?", (st["id"], cid)):
        flash("Already enrolled.", "warning"); return redirect(url_for("courses_list"))
    ex("INSERT INTO enrollments(student_id,course_id,enrolled_at) VALUES(?,?,?)", (st["id"],cid,now_iso()))
    flash(f"Enrolled in {c['code']} — {c['title']}!", "success")
    return redirect(url_for("courses_list"))


@app.route("/courses/<int:cid>/assign", methods=["GET","POST"])
@admin_required
def course_assign(cid):
    c = q1("SELECT * FROM courses WHERE id=?", (cid,))
    if not c: abort(404)
    if request.method == "POST":
        sf_id = int(request.form.get("staff_id",0))
        role  = request.form.get("role","professor")
        if q1("SELECT id FROM course_assignments WHERE staff_id=? AND course_id=?", (sf_id,cid)):
            flash("Already assigned.", "warning")
        else:
            ex("INSERT INTO course_assignments(staff_id,course_id,role) VALUES(?,?,?)", (sf_id,cid,role))
            flash("Staff assigned.", "success")
        return redirect(url_for("course_assign", cid=cid))

    assigned = q("""SELECT s.*,ca.id ca_id,ca.role ar FROM course_assignments ca
        JOIN staff s ON s.id=ca.staff_id WHERE ca.course_id=?""", (cid,))
    all_staff = q("SELECT * FROM staff ORDER BY name")

    staff_opts = "".join(f'<option value="{s["id"]}">{s["name"]} ({s["staff_id"]})</option>' for s in all_staff)
    assigned_html = "".join(f"""
      <div style="display:flex;align-items:center;gap:.6rem;background:#f8faff;border:1px solid #e8edf8;
          border-radius:.55rem;padding:.65rem .9rem;margin-bottom:.5rem;">
        <div style="width:28px;height:28px;background:var(--navy);color:#fff;border-radius:50%;
          display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;">{s['name'][0].upper()}</div>
        <div>
          <div style="font-weight:600;font-size:.85rem;">{s['name']}</div>
          <div style="display:flex;gap:.3rem;margin-top:.2rem;">
            <span class="badge badge-navy">{s['ar'].title()}</span>
            <span class="badge badge-gray">{s['staff_id']}</span>
          </div>
        </div>
      </div>""" for s in assigned) or '<div class="empty-state" style="padding:1.5rem;"><p style="font-size:.83rem;color:var(--muted);">None assigned yet.</p></div>'

    inner = f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;max-width:780px;">
      <div class="card card-p">
        <h3 class="serif" style="font-size:1rem;margin-bottom:1rem;">Assign Staff to {c['code']}</h3>
        <form method="POST">
          <div class="form-group">
            <label class="form-label">Staff Member</label>
            <select name="staff_id" class="form-control" required>
              <option value="">— Select —</option>{staff_opts}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Role</label>
            <select name="role" class="form-control">
              <option value="professor">Professor</option>
              <option value="ta">Teaching Assistant</option>
            </select>
          </div>
          <button class="btn btn-gold"><i data-lucide="user-plus" style="width:14px;height:14px;"></i>Assign</button>
        </form>
      </div>
      <div class="card card-p">
        <h3 class="serif" style="font-size:1rem;margin-bottom:1rem;">Currently Assigned</h3>
        {assigned_html}
      </div>
    </div>
    <a href="{url_for('courses_list')}" class="btn btn-outline" style="margin-top:1rem;">
      <i data-lucide="arrow-left" style="width:13px;height:13px;"></i>Back to Courses</a>"""
    return render_template_string(page(f"Assign Staff — {c['code']}","courses",inner,f"Assign Staff · {c['code']}","Courses · Staff Assignment"))


def _course_form(c=None):
    DEPTS = ["Computer Science","Computer Engineering","Electrical Engineering",
             "Mechanical Engineering","Civil Engineering","Information Systems"]
    dept_opts = "".join(f'<option value="{d}" {"selected" if c and c["department"]==d else ""}>{d}</option>' for d in DEPTS)
    code_field = f'<div style="background:#f8faff;border:1px solid #e8edf8;border-radius:.5rem;padding:.65rem .85rem;margin-bottom:1rem;"><div style="font-size:.7rem;color:var(--muted);font-weight:600;">Course Code</div><div style="font-family:monospace;font-weight:700;font-size:1.1rem;color:var(--navy);">{c["code"]}</div></div>' if c else """
      <div class="form-group">
        <label class="form-label">Course Code *</label>
        <input type="text" name="code" required class="form-control" placeholder="e.g. CSE342" maxlength="20" style="text-transform:uppercase;">
      </div>"""
    sel = lambda val, lbl: f'<option value="{val}" {"selected" if c and c["course_type"]==val else ""}>{lbl}</option>'
    return f"""
    <div style="max-width:520px;"><div class="card card-p">
      <form method="POST">
        {code_field}
        <div class="form-group">
          <label class="form-label">Title *</label>
          <input type="text" name="title" required class="form-control" value="{c['title'] if c else ''}" placeholder="Course title">
        </div>
        <div class="form-group">
          <label class="form-label">Description</label>
          <textarea name="description" rows="3" class="form-control" placeholder="Brief description…">{c['description'] if c else ''}</textarea>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
          <div class="form-group">
            <label class="form-label">Type</label>
            <select name="course_type" class="form-control">{sel('core','Core')}{sel('elective','Elective')}</select>
          </div>
          <div class="form-group">
            <label class="form-label">Capacity</label>
            <input type="number" name="capacity" min="1" max="500" class="form-control" value="{c['capacity'] if c else 50}">
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Department</label>
          <select name="department" class="form-control"><option value="">— Select —</option>{dept_opts}</select>
        </div>
        <hr class="divider">
        <div style="display:flex;gap:.6rem;">
          <button class="btn btn-gold">
            <i data-lucide="{'save' if c else 'book-plus'}" style="width:14px;height:14px;"></i>
            {'Save Changes' if c else 'Add to Catalog'}
          </button>
          <a href="{url_for('courses_list')}" class="btn btn-outline">Cancel</a>
        </div>
      </form>
    </div></div>"""


# ═══════════════════════════════════════════════════════════════
#  FACILITIES — ROOMS & BOOKINGS  (Epic 1)
# ═══════════════════════════════════════════════════════════════
@app.route("/rooms")
@login_required
def rooms_list():
    date_filter = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    rooms       = q("SELECT * FROM rooms ORDER BY room_number")
    bookings    = q("""SELECT b.*,s.name staff_name FROM bookings b
        JOIN staff s ON s.id=b.staff_id WHERE b.date=? ORDER BY b.start_time""", (date_filter,))
    schedule: dict = {}
    for bk in bookings:
        schedule.setdefault(bk["room_id"], []).append(bk)

    role = session.get("role","")
    cards = ""
    for r in rooms:
        bks  = schedule.get(r["id"], [])
        ico  = "flask-conical" if r["room_type"]=="lab" else "door-open"
        status_badge = '<span class="badge badge-red">Booked</span>' if bks else '<span class="badge badge-green">Free</span>'
        bk_html = "".join(f"""
          <div class="room-busy">
            <div style="font-weight:600;font-size:.8rem;">{bk['title']}</div>
            <div style="font-size:.73rem;color:var(--muted);">{bk['start_time']} – {bk['end_time']} · {bk['staff_name']}</div>
          </div>""" for bk in bks) if bks else f'<div class="room-free"><span style="font-size:.8rem;font-weight:600;color:#166534;">Available all day</span></div>'

        cards += f"""
        <div class="card card-p">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.85rem;">
            <div style="display:flex;align-items:center;gap:.65rem;">
              <div style="width:36px;height:36px;background:var(--navy);border-radius:.5rem;
                display:flex;align-items:center;justify-content:center;">
                <i data-lucide="{ico}" style="width:16px;height:16px;color:#fff;"></i>
              </div>
              <div>
                <div style="font-weight:700;font-size:.92rem;">{r['room_number']}</div>
                <div style="font-size:.72rem;color:var(--muted);">{r['room_type'].title()} · Cap {r['capacity']}</div>
              </div>
            </div>
            {status_badge}
          </div>
          {bk_html}
        </div>"""

    book_btn = f'<a href="{url_for("room_book")}" class="btn btn-gold"><i data-lucide="calendar-plus" style="width:14px;height:14px;"></i>Book a Room</a>' if role in ("admin","staff","professor","ta") else ""

    inner = f"""
    <div class="section-header">
      <form method="GET" style="display:flex;align-items:center;gap:.65rem;">
        <label style="font-size:.82rem;font-weight:600;color:var(--muted);">Date:</label>
        <input type="date" name="date" value="{date_filter}" class="form-control" style="width:160px;" onchange="this.form.submit()">
        <div style="display:flex;gap:.65rem;margin-left:.5rem;">
          <span style="font-size:.73rem;display:flex;align-items:center;gap:.35rem;">
            <span style="width:10px;height:10px;background:#dcfce7;border:1px solid #86efac;border-radius:2px;display:inline-block;"></span>Free
          </span>
          <span style="font-size:.73rem;display:flex;align-items:center;gap:.35rem;">
            <span style="width:10px;height:10px;background:#fee2e2;border:1px solid #fca5a5;border-radius:2px;display:inline-block;"></span>Occupied
          </span>
        </div>
      </form>
      {book_btn}
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:1rem;">
      {cards}
    </div>"""
    return render_template_string(page("Room Schedule","rooms",inner,"Room Availability","Facilities Module · Real-Time Schedule"))


@app.route("/rooms/book", methods=["GET","POST"])
@login_required
@role_required("admin","staff","professor","ta")
def room_book():
    uid = session.get("user_id")
    sf  = q1("SELECT * FROM staff WHERE user_id=?", (uid,))
    if not sf and session["role"] != "admin":
        flash("Staff profile required to book rooms.", "danger"); return redirect(url_for("rooms_list"))
    all_staff = q("SELECT * FROM staff ORDER BY name") if session["role"]=="admin" else []

    if request.method == "POST":
        room_id    = int(request.form.get("room_id",0) or 0)
        title      = request.form.get("title","").strip()
        date       = request.form.get("date","").strip()
        start_time = request.form.get("start_time","").strip()
        end_time   = request.form.get("end_time","").strip()
        staff_id   = int(request.form.get("staff_id", sf["id"] if sf else 0) or 0)

        if not all([room_id, title, date, start_time, end_time, staff_id]):
            flash("All fields are required.", "danger")
        elif start_time >= end_time:
            flash("Start time must be before end time.", "danger")
        elif q1("SELECT id FROM bookings WHERE room_id=? AND date=? AND NOT (end_time<=? OR start_time>=?)",
                (room_id,date,start_time,end_time)):
            flash("Room already booked during that time slot.", "danger")
        else:
            ts = now_iso()
            ex("INSERT INTO bookings(room_id,staff_id,title,date,start_time,end_time,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
               (room_id,staff_id,title,date,start_time,end_time,ts,ts))
            flash("Room booked successfully!", "success")
            return redirect(url_for("my_bookings"))
    return render_template_string(page("Book a Room","room_book",_booking_form(None,all_staff,sf),"Book a Room","Facilities · New Booking"))


@app.route("/bookings")
@login_required
def my_bookings():
    uid  = session.get("user_id")
    role = session.get("role","")
    if role == "admin":
        bks = q("""SELECT b.*,r.room_number,r.room_type,s.name staff_name
            FROM bookings b JOIN rooms r ON r.id=b.room_id JOIN staff s ON s.id=b.staff_id
            ORDER BY b.date DESC,b.start_time""")
    else:
        sf = q1("SELECT id FROM staff WHERE user_id=?", (uid,))
        bks = q("""SELECT b.*,r.room_number,r.room_type,s.name staff_name
            FROM bookings b JOIN rooms r ON r.id=b.room_id JOIN staff s ON s.id=b.staff_id
            WHERE b.staff_id=? ORDER BY b.date DESC,b.start_time""",
            (sf["id"],)) if sf else []

    rows = ""
    today = datetime.now().strftime("%Y-%m-%d")
    for bk in bks:
        past   = bk["date"] < today
        status = '<span class="badge badge-gray">Past</span>' if past else '<span class="badge badge-green">Upcoming</span>'
        rt_ic  = "flask-conical" if bk["room_type"]=="lab" else "door-open"
        actions = ""
        if not past:
            uid_sf = q1("SELECT id FROM staff WHERE user_id=?", (uid,))
            if role == "admin" or (uid_sf and uid_sf["id"] == bk["staff_id"]):
                actions = f"""
                  <a href="{url_for('booking_edit',bid=bk['id'])}" class="btn btn-outline btn-xs">
                    <i data-lucide="pencil" style="width:11px;height:11px;"></i>Edit</a>
                  <form method="POST" action="{url_for('booking_cancel',bid=bk['id'])}" style="display:inline;"
                        onsubmit="return confirm('Cancel this booking?')">
                    <button class="btn btn-danger btn-xs">
                      <i data-lucide="x-circle" style="width:11px;height:11px;"></i>Cancel</button>
                  </form>"""
        rows += f"""<tr>
          <td><i data-lucide="{rt_ic}" style="width:13px;height:13px;vertical-align:middle;margin-right:.3rem;color:var(--navy);"></i><strong>{bk['room_number']}</strong></td>
          <td style="font-weight:500;">{bk['title']}</td>
          <td>{bk['date']}</td>
          <td style="color:var(--muted);">{bk['start_time']} – {bk['end_time']}</td>
          <td style="color:var(--muted);">{bk['staff_name']}</td>
          <td>{status}</td>
          <td><div style="display:flex;gap:.3rem;justify-content:flex-end;">{actions}</div></td>
        </tr>"""

    if not bks:
        rows = f"""<tr><td colspan="7" class="empty-state">
          <i data-lucide="calendar-x" style="width:34px;height:34px;" class="ic"></i>
          <p style="font-size:.85rem;color:var(--muted);">No bookings found.</p>
          {'<a href="'+url_for("room_book")+'" class="btn btn-gold" style="margin-top:.75rem;">Book a Room</a>' if role in ("admin","staff","professor","ta") else ''}
        </td></tr>"""

    book_btn = f'<a href="{url_for("room_book")}" class="btn btn-gold"><i data-lucide="calendar-plus" style="width:14px;height:14px;"></i>Book a Room</a>' if session.get("role") in ("admin","staff","professor","ta") else ""
    inner = f"""
    <div class="section-header">
      <p class="page-sub">{len(bks)} booking(s)</p>
      {book_btn}
    </div>
    <div class="table-wrap">
      <table class="ums-table">
        <thead><tr>
          <th>Room</th><th>Session</th><th>Date</th><th>Time</th><th>Booked By</th><th>Status</th><th style="text-align:right;">Actions</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    return render_template_string(page("Bookings","bookings",inner,"Room Bookings","Facilities · My Bookings"))


@app.route("/bookings/<int:bid>/edit", methods=["GET","POST"])
@login_required
@role_required("admin","staff","professor","ta")
def booking_edit(bid):
    bk  = q1("SELECT b.*,r.room_number FROM bookings b JOIN rooms r ON r.id=b.room_id WHERE b.id=?", (bid,))
    if not bk: abort(404)
    uid = session.get("user_id")
    sf  = q1("SELECT id FROM staff WHERE user_id=?", (uid,))
    if session["role"] != "admin" and (not sf or sf["id"] != bk["staff_id"]):
        flash("Access denied.", "danger"); return redirect(url_for("my_bookings"))

    if request.method == "POST":
        room_id    = int(request.form.get("room_id", bk["room_id"]))
        title      = request.form.get("title","").strip()
        date       = request.form.get("date","").strip()
        start_time = request.form.get("start_time","").strip()
        end_time   = request.form.get("end_time","").strip()
        if start_time >= end_time:
            flash("Start time must be before end time.", "danger")
        elif q1("SELECT id FROM bookings WHERE room_id=? AND date=? AND id!=? AND NOT (end_time<=? OR start_time>=?)",
                (room_id,date,bid,start_time,end_time)):
            flash("Time slot conflict.", "danger")
        else:
            ex("UPDATE bookings SET room_id=?,title=?,date=?,start_time=?,end_time=?,updated_at=? WHERE id=?",
               (room_id,title,date,start_time,end_time,now_iso(),bid))
            flash("Booking updated.", "success")
            return redirect(url_for("my_bookings"))
    return render_template_string(page("Edit Booking","bookings",_booking_form(bk,[],sf),"Edit Booking","Bookings · Edit"))


@app.route("/bookings/<int:bid>/cancel", methods=["POST"])
@login_required
def booking_cancel(bid):
    bk  = q1("SELECT * FROM bookings WHERE id=?", (bid,))
    if not bk: abort(404)
    uid = session.get("user_id")
    sf  = q1("SELECT id FROM staff WHERE user_id=?", (uid,))
    if session["role"] != "admin" and (not sf or sf["id"] != bk["staff_id"]):
        flash("Access denied.", "danger"); return redirect(url_for("my_bookings"))
    ex("DELETE FROM bookings WHERE id=?", (bid,))
    flash("Booking cancelled.", "success")
    return redirect(url_for("my_bookings"))


def _booking_form(bk=None, all_staff=None, sf=None):
    rooms = q("SELECT * FROM rooms ORDER BY room_number")
    room_opts = "".join(
        f'<option value="{r["id"]}" {"selected" if bk and bk["room_id"]==r["id"] else ""}>'
        f'{r["room_number"]} ({r["room_type"].title()}, cap {r["capacity"]})</option>'
        for r in rooms)
    staff_sel = ""
    if all_staff and session.get("role") == "admin":
        staff_opts = "".join(f'<option value="{s["id"]}">{s["name"]} ({s["staff_id"]})</option>' for s in all_staff)
        staff_sel = f"""<div class="form-group">
          <label class="form-label">Booking For (Staff) *</label>
          <select name="staff_id" class="form-control" required><option value="">— Select —</option>{staff_opts}</select>
        </div>"""
    elif sf:
        staff_sel = f'<input type="hidden" name="staff_id" value="{sf["id"]}">'
    return f"""
    <div style="max-width:500px;"><div class="card card-p">
      <form method="POST">
        <div class="form-group">
          <label class="form-label">Room *</label>
          <select name="room_id" class="form-control" required><option value="">— Select room —</option>{room_opts}</select>
        </div>
        {staff_sel}
        <div class="form-group">
          <label class="form-label">Session Title *</label>
          <input type="text" name="title" required class="form-control"
                 value="{bk['title'] if bk else ''}" placeholder="e.g. CSE342 Lecture, Lab Session…">
        </div>
        <div class="form-group">
          <label class="form-label">Date *</label>
          <input type="date" name="date" required class="form-control" value="{bk['date'] if bk else ''}">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
          <div class="form-group">
            <label class="form-label">Start Time *</label>
            <input type="time" name="start_time" required class="form-control" value="{bk['start_time'] if bk else ''}">
          </div>
          <div class="form-group">
            <label class="form-label">End Time *</label>
            <input type="time" name="end_time" required class="form-control" value="{bk['end_time'] if bk else ''}">
          </div>
        </div>
        <hr class="divider">
        <div style="display:flex;gap:.6rem;">
          <button class="btn btn-gold">
            <i data-lucide="{'save' if bk else 'calendar-plus'}" style="width:14px;height:14px;"></i>
            {'Update Booking' if bk else 'Confirm Booking'}
          </button>
          <a href="{url_for('my_bookings')}" class="btn btn-outline">Cancel</a>
        </div>
      </form>
    </div></div>"""


# ═══════════════════════════════════════════════════════════════
#  ANNOUNCEMENTS  (Community — Epic 4)
# ═══════════════════════════════════════════════════════════════
@app.route("/announcements")
@login_required
def announcements_list():
    anns = q("SELECT a.*,u.full_name author FROM announcements a LEFT JOIN users u ON u.id=a.created_by ORDER BY a.created_at DESC")
    role = session.get("role","")

    cards = ""
    for a in anns:
        actions = ""
        if role == "admin":
            actions = f"""
              <a href="{url_for('announcement_edit',aid=a['id'])}" class="btn btn-outline btn-xs">
                <i data-lucide="pencil" style="width:11px;height:11px;"></i>Edit</a>
              <form method="POST" action="{url_for('announcement_delete',aid=a['id'])}" style="display:inline;"
                    onsubmit="return confirm('Delete this announcement?')">
                <button class="btn btn-danger btn-xs">
                  <i data-lucide="trash-2" style="width:11px;height:11px;"></i>Delete</button>
              </form>"""
        cards += f"""
        <div class="card card-p" style="margin-bottom:.85rem;">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;">
            <div style="flex:1;">
              <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem;">
                <i data-lucide="megaphone" style="width:14px;height:14px;color:var(--gold);"></i>
                <h3 style="font-weight:700;font-size:.95rem;">{a['title']}</h3>
              </div>
              <p style="font-size:.85rem;color:var(--text);line-height:1.55;">{a['body']}</p>
              <div style="font-size:.72rem;color:#94a3b8;margin-top:.65rem;">
                Posted {a['created_at'][:10]}
                {' by '+a['author'] if a['author'] else ''}
                {' · Updated '+a['updated_at'][:10] if a['updated_at']!=a['created_at'] else ''}
              </div>
            </div>
            <div style="display:flex;gap:.4rem;flex-shrink:0;">{actions}</div>
          </div>
        </div>"""

    if not anns:
        cards = '<div class="empty-state"><i data-lucide="bell-off" style="width:34px;height:34px;" class="ic"></i><p style="font-size:.85rem;color:var(--muted);">No announcements yet.</p></div>'

    add_btn = f'<a href="{url_for("announcement_new")}" class="btn btn-gold"><i data-lucide="plus" style="width:14px;height:14px;"></i>Post Announcement</a>' if role=="admin" else ""
    inner = f"""
    <div class="section-header"><p class="page-sub">{len(anns)} announcement(s)</p>{add_btn}</div>
    <div style="max-width:780px;">{cards}</div>"""
    return render_template_string(page("Announcements","announcements",inner,"Announcements","Community Module · University-Wide Updates"))


@app.route("/announcements/new", methods=["GET","POST"])
@admin_required
def announcement_new():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        body  = request.form.get("body","").strip()
        if not title or not body:
            flash("Title and body are required.", "danger")
        else:
            ts = now_iso(); uid = session.get("user_id")
            ex("INSERT INTO announcements(title,body,created_by,created_at,updated_at) VALUES(?,?,?,?,?)", (title,body,uid,ts,ts))
            flash("Announcement posted.", "success")
            return redirect(url_for("announcements_list"))
    inner = _ann_form()
    return render_template_string(page("Post Announcement","announcements",inner,"Post Announcement","Announcements · New"))


@app.route("/announcements/<int:aid>/edit", methods=["GET","POST"])
@admin_required
def announcement_edit(aid):
    a = q1("SELECT * FROM announcements WHERE id=?", (aid,))
    if not a: abort(404)
    if request.method == "POST":
        title = request.form.get("title","").strip()
        body  = request.form.get("body","").strip()
        ex("UPDATE announcements SET title=?,body=?,updated_at=? WHERE id=?", (title,body,now_iso(),aid))
        flash("Announcement updated.", "success")
        return redirect(url_for("announcements_list"))
    inner = _ann_form(a)
    return render_template_string(page("Edit Announcement","announcements",inner,"Edit Announcement","Announcements · Edit"))


@app.route("/announcements/<int:aid>/delete", methods=["POST"])
@admin_required
def announcement_delete(aid):
    ex("DELETE FROM announcements WHERE id=?", (aid,))
    flash("Announcement deleted.", "success")
    return redirect(url_for("announcements_list"))


def _ann_form(a=None):
    return f"""
    <div style="max-width:620px;"><div class="card card-p">
      <form method="POST">
        <div class="form-group">
          <label class="form-label">Title *</label>
          <input type="text" name="title" required class="form-control" value="{a['title'] if a else ''}" placeholder="Announcement title">
        </div>
        <div class="form-group">
          <label class="form-label">Body *</label>
          <textarea name="body" required rows="6" class="form-control" placeholder="Write announcement…">{a['body'] if a else ''}</textarea>
        </div>
        <hr class="divider">
        <div style="display:flex;gap:.6rem;">
          <button class="btn btn-gold">
            <i data-lucide="{'save' if a else 'megaphone'}" style="width:14px;height:14px;"></i>
            {'Save Changes' if a else 'Post Announcement'}
          </button>
          <a href="{url_for('announcements_list')}" class="btn btn-outline">Cancel</a>
        </div>
      </form>
    </div></div>"""


# ═══════════════════════════════════════════════════════════════
#  EVENTS & DEADLINES  (Community — Epic 4)
# ═══════════════════════════════════════════════════════════════
@app.route("/events")
@login_required
def events_list():
    evts = q("SELECT e.*,u.full_name author FROM events e LEFT JOIN users u ON u.id=e.created_by ORDER BY e.event_date")
    role = session.get("role","")
    today = datetime.now().strftime("%Y-%m-%d")

    rows = ""
    for e in evts:
        past   = e["event_date"] < today
        status = '<span class="badge badge-gray">Past</span>' if past else '<span class="badge badge-green">Upcoming</span>'
        del_btn = ""
        if role == "admin":
            del_btn = f"""<form method="POST" action="{url_for('event_delete',eid=e['id'])}" style="display:inline;"
              onsubmit="return confirm('Delete this event?')">
              <button class="btn btn-danger btn-xs"><i data-lucide="trash-2" style="width:11px;height:11px;"></i>Delete</button>
            </form>"""
        rows += f"""<tr>
          <td style="font-weight:700;font-family:monospace;">{e['event_date']}</td>
          <td style="font-weight:600;">{e['title']}</td>
          <td style="color:var(--muted);">{e['description'][:80]+('…' if len(e['description'])>80 else '') if e['description'] else '—'}</td>
          <td>{status}</td>
          <td style="text-align:right;">{del_btn}</td>
        </tr>"""

    if not evts:
        rows = '<tr><td colspan="5" class="empty-state"><i data-lucide="calendar-x" style="width:34px;height:34px;" class="ic"></i><p style="font-size:.85rem;color:var(--muted);">No events added yet.</p></td></tr>'

    add_btn = f'<a href="{url_for("event_new")}" class="btn btn-gold"><i data-lucide="plus" style="width:14px;height:14px;"></i>Add Event</a>' if role=="admin" else ""
    inner = f"""
    <div class="section-header"><p class="page-sub">{len(evts)} event(s)</p>{add_btn}</div>
    <div class="table-wrap">
      <table class="ums-table">
        <thead><tr><th>Date</th><th>Title</th><th>Description</th><th>Status</th><th style="text-align:right;">Actions</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""
    return render_template_string(page("Events","events",inner,"Events & Deadlines","Community Module · Academic Calendar"))


@app.route("/events/new", methods=["GET","POST"])
@admin_required
def event_new():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        desc  = request.form.get("description","").strip()
        date  = request.form.get("event_date","").strip()
        if not title or not date:
            flash("Title and date are required.", "danger")
        else:
            ex("INSERT INTO events(title,description,event_date,created_by,created_at) VALUES(?,?,?,?,?)",
               (title,desc,date,session.get("user_id"),now_iso()))
            flash("Event added.", "success")
            return redirect(url_for("events_list"))
    inner = f"""
    <div style="max-width:500px;"><div class="card card-p">
      <form method="POST">
        <div class="form-group">
          <label class="form-label">Title *</label>
          <input type="text" name="title" required class="form-control" placeholder="Event or deadline name">
        </div>
        <div class="form-group">
          <label class="form-label">Date *</label>
          <input type="date" name="event_date" required class="form-control">
        </div>
        <div class="form-group">
          <label class="form-label">Description</label>
          <textarea name="description" rows="3" class="form-control" placeholder="Optional details…"></textarea>
        </div>
        <hr class="divider">
        <div style="display:flex;gap:.6rem;">
          <button class="btn btn-gold"><i data-lucide="calendar-plus" style="width:14px;height:14px;"></i>Add Event</button>
          <a href="{url_for('events_list')}" class="btn btn-outline">Cancel</a>
        </div>
      </form>
    </div></div>"""
    return render_template_string(page("Add Event","events",inner,"Add Event / Deadline","Events · New"))


@app.route("/events/<int:eid>/delete", methods=["POST"])
@admin_required
def event_delete(eid):
    ex("DELETE FROM events WHERE id=?", (eid,))
    flash("Event removed.", "success")
    return redirect(url_for("events_list"))


# ═══════════════════════════════════════════════════════════════
#  PROFILE / PERSONAL DASHBOARD  (Staff Module — Epic 3)
# ═══════════════════════════════════════════════════════════════
@app.route("/profile")
@login_required
def profile():
    uid  = session.get("user_id")
    role = session.get("role","")
    user = q1("SELECT * FROM users WHERE id=?", (uid,))
    extra, courses = None, []

    if role == "student":
        extra = q1("SELECT * FROM students WHERE user_id=?", (uid,))
        if extra:
            courses = q("""SELECT c.* FROM enrollments e JOIN courses c ON c.id=e.course_id
                WHERE e.student_id=? ORDER BY c.code""", (extra["id"],))
    elif role in ("staff","professor","ta"):
        extra = q1("SELECT * FROM staff WHERE user_id=?", (uid,))
        if extra:
            courses = q("""SELECT c.*,ca.role ar,ca.resp_notes FROM course_assignments ca
                JOIN courses c ON c.id=ca.course_id WHERE ca.staff_id=? ORDER BY c.code""", (extra["id"],))

    av = (user["full_name"] or user["username"] or "?")[0].upper()
    role_color = {"admin":"var(--navy)","student":"#166534","professor":"#854d0e","ta":"#6b21a8"}.get(role,"#475569")

    # Info fields
    def row(ic, lbl, val):
        return f"""<div style="display:flex;align-items:flex-start;gap:.75rem;padding:.65rem 0;border-bottom:1px solid var(--border);">
          <i data-lucide="{ic}" style="width:15px;height:15px;color:var(--muted);margin-top:.1rem;flex-shrink:0;"></i>
          <div><div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;font-weight:700;color:var(--muted);">{lbl}</div>
          <div style="font-size:.88rem;margin-top:.1rem;">{val or '<span style="color:#94a3b8;">Not set</span>'}</div></div>
        </div>"""

    info_rows = row("user","Username", user["username"]) + row("mail","Email", user["email"]) + row("building","Department",user["department"])
    if extra:
        if role=="student":
            info_rows += row("hash","Student ID", extra["student_id"]) + row("calendar","Year", f"Year {extra['year']}" if extra['year'] else None)
        else:
            info_rows += row("hash","Staff ID", extra["staff_id"]) + row("phone","Phone", extra["phone"]) + row("clock","Office Hours", extra["office_hours"])

    # Courses
    def course_card(c):
        ct_badge = '<span class="badge badge-green">Core</span>' if c["course_type"]=="core" else '<span class="badge badge-gold">Elective</span>'
        extra_info = f'<div style="font-size:.75rem;color:var(--muted);margin-top:.25rem;">Role: {c["ar"].title()} — {c["resp_notes"] or "No responsibilities set"}</div>' if role in ("staff","professor","ta") else ""
        return f"""<div style="background:#f8faff;border:1px solid #e8edf8;border-radius:.55rem;padding:.7rem .9rem;margin-bottom:.5rem;">
          <div style="display:flex;align-items:center;gap:.5rem;">
            <span style="font-family:monospace;font-weight:700;color:var(--navy);">{c['code']}</span>
            {ct_badge}
          </div>
          <div style="font-weight:600;font-size:.88rem;margin-top:.2rem;">{c['title']}</div>
          {extra_info}
        </div>"""

    courses_html = "".join(course_card(c) for c in courses) if courses else \
        '<div style="font-size:.83rem;color:#94a3b8;padding:.75rem 0;">No courses yet.</div>'

    inner = f"""
    <div style="display:grid;grid-template-columns:300px 1fr;gap:1.5rem;max-width:900px;">
      <!-- Profile card -->
      <div>
        <div class="card card-p" style="text-align:center;margin-bottom:1rem;">
          <div style="width:72px;height:72px;background:var(--navy);color:#fff;border-radius:50%;
            display:flex;align-items:center;justify-content:center;font-size:2rem;font-weight:700;
            margin:0 auto .85rem;font-family:'Fraunces',serif;">{av}</div>
          <div style="font-family:'Fraunces',serif;font-size:1.25rem;">{user['full_name'] or user['username']}</div>
          <div style="display:inline-block;background:{role_color}20;color:{role_color};
            font-size:.72rem;font-weight:700;padding:.25rem .75rem;border-radius:99px;
            text-transform:capitalize;margin-top:.4rem;">{role}</div>
          <hr class="divider">
          <div style="text-align:left;">{info_rows}</div>
        </div>
      </div>
      <!-- Courses -->
      <div class="card card-p">
        <h3 class="serif" style="font-size:1rem;margin-bottom:.85rem;">
          {'My Enrolled Courses' if role=='student' else 'My Teaching Assignments'}
        </h3>
        {courses_html}
        {'<div style="margin-top:1rem;"><a href="'+url_for("courses_list")+'" class="btn btn-gold btn-sm"><i data-lucide="book-plus" style="width:13px;height:13px;"></i>Browse Courses</a></div>' if role=='student' else ''}
      </div>
    </div>"""
    return render_template_string(page("My Profile","profile",inner,"My Profile","Personal Dashboard"))


# ═══════════════
#  ENTRY POINT
# ═══════════════
if __name__ == "__main__":
    init_db()
    port = 5050
    url  = f"http://127.0.0.1:{port}"

    def open_browser():
        webbrowser.open_new(url)

    threading.Timer(1.2, open_browser).start()
    print(f"\n{'='*58}")
    print(f"  UniManage — University Management System")
    print(f"  Running at: {url}")
    print(f"  Admin login: admin / admin123")
    print(f"{'='*58}\n")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
