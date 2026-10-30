"""Flask backend: auth, chatbot API, history, trend dashboard, warnings, admin.

Run:  python app.py   ->  http://127.0.0.1:5000
"""
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import engine

BASE = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
HOSTED = bool(os.environ.get("VERCEL"))
# ponytail: Vercel only allows writes to /tmp, per instance and wiped on restart.
# Real persistence needs a hosted database (Postgres/Turso) instead of SQLite.
app.config["DATABASE"] = os.environ.get("DATABASE") or ("/tmp/wellbeing.db" if HOSTED else str(BASE / "instance" / "wellbeing.db"))
app.config.update(SESSION_COOKIE_SECURE=HOSTED, SESSION_COOKIE_SAMESITE="Lax")
MIN_GROUP = 3  # admin stats hide any group with fewer distinct employees (k-anonymity)

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    department TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee' CHECK (role IN ('employee','admin')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sender TEXT NOT NULL CHECK (sender IN ('user','bot')),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    category TEXT NOT NULL,
    confidence REAL NOT NULL,
    stress_level INTEGER NOT NULL CHECK (stress_level BETWEEN 1 AND 10),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    rec_key TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_assess_user_time ON assessments(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_msg_user_time ON messages(user_id, created_at);
"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def db():
    if "db" not in g:
        Path(app.config["DATABASE"]).parent.mkdir(exist_ok=True)
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    with app.app_context():
        db().executescript(SCHEMA)


# ---------- auth / security helpers ----------
def current_user():
    uid, email = session.get("uid"), session.get("email")
    # email check: separate hosted instances can give different people the same id
    return db().execute("SELECT * FROM users WHERE id=? AND email=?", (uid, email)).fetchone() if uid else None


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                return redirect(url_for("login", next=request.path))
            if role and u["role"] != role:
                abort(403)
            g.user = u
            return fn(*a, **kw)
        return wrapper
    return deco


@app.before_request
def csrf_protect():
    session.setdefault("csrf", secrets.token_hex(16))
    if request.method == "POST":
        token = request.form.get("csrf") or request.headers.get("X-CSRF")
        if token != session["csrf"]:
            abort(400, "Invalid CSRF token")


@app.context_processor
def inject():
    u = current_user()
    ctx = {"user": u, "csrf": session.get("csrf"), "LABELS": engine.LABELS, "unread": 0, "streak": 0,
           "hosted": HOSTED}
    if u and u["role"] == "employee":
        ctx["unread"] = db().execute("SELECT COUNT(*) FROM warnings WHERE user_id=? AND acknowledged=0",
                                     (u["id"],)).fetchone()[0]
        ctx["streak"] = user_summary(u["id"])["streak"]
    return ctx


def user_summary(uid):
    rows = db().execute("SELECT created_at, stress_level, category FROM assessments WHERE user_id=? "
                        "ORDER BY created_at", (uid,)).fetchall()
    return engine.summary([tuple(r) for r in rows])


# ---------- pages ----------
@app.route("/")
def home():
    u = current_user()
    if not u:
        return render_template("index.html")
    if u["role"] == "admin":
        return redirect(url_for("admin"))
    return render_template("home.html", s=user_summary(u["id"]))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        dept = request.form.get("department", "").strip()
        pw = request.form.get("password", "")
        if not name or "@" not in email or len(pw) < 8:
            flash("Enter a name, a valid email and a password of at least 8 characters.", "danger")
        else:
            try:
                db().execute("INSERT INTO users(name,email,department,password_hash,created_at) VALUES(?,?,?,?,?)",
                             (name, email, dept, generate_password_hash(pw), now()))
                db().commit()
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session["uid"], session["email"] = u["id"], u["email"]
            nxt = request.args.get("next", "")
            if not nxt.startswith("/") or nxt.startswith("//"):  # no open redirects
                nxt = url_for("home")
            return redirect(nxt)
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/chat")
@login_required("employee")
def chat():
    msgs = db().execute("SELECT sender,text,created_at FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 30",
                        (g.user["id"],)).fetchall()[::-1]
    counts = dict(db().execute("SELECT category, COUNT(*) FROM assessments WHERE user_id=? GROUP BY category",
                               (g.user["id"],)).fetchall())
    return render_template("chat.html", messages=msgs, counts=counts)


@app.route("/history")
@login_required("employee")
def history():
    rows = db().execute("""SELECT a.id, a.category, a.confidence, a.stress_level, a.created_at, m.text
                           FROM assessments a LEFT JOIN messages m ON m.id=a.message_id
                           WHERE a.user_id=? ORDER BY a.created_at DESC LIMIT 200""", (g.user["id"],)).fetchall()
    recs = {}
    for r in db().execute("SELECT assessment_id, text FROM recommendations WHERE user_id=?", (g.user["id"],)):
        recs.setdefault(r["assessment_id"], []).append(r["text"])
    return render_template("history.html", rows=rows, recs=recs)


@app.route("/dashboard")
@login_required("employee")
def dashboard():
    return render_template("dashboard.html")


@app.route("/warnings", methods=["GET", "POST"])
@login_required("employee")
def warnings():
    if request.method == "POST":
        db().execute("UPDATE warnings SET acknowledged=1 WHERE user_id=?", (g.user["id"],))
        db().commit()
        return redirect(url_for("warnings"))
    rows = db().execute("SELECT * FROM warnings WHERE user_id=? ORDER BY created_at DESC", (g.user["id"],)).fetchall()
    return render_template("warnings.html", rows=rows)


@app.route("/admin")
@login_required("admin")
def admin():
    return render_template("admin.html", min_group=MIN_GROUP)


# ---------- JSON APIs ----------
@app.post("/api/chat")
@login_required("employee")
def api_chat():
    data = request.get_json(silent=True) or {}
    text = str(data.get("message", "")).strip()[:1000]
    if not text:
        return jsonify(error="Message is empty"), 400
    rating = data.get("self_rating")
    rating = int(rating) if str(rating).isdigit() and 1 <= int(rating) <= 10 else None
    uid, conn, ts = g.user["id"], db(), now()
    mid = conn.execute("INSERT INTO messages(user_id,sender,text,created_at) VALUES(?,?,?,?)",
                       (uid, "user", text, ts)).lastrowid

    if engine.is_crisis(text):
        conn.execute("INSERT INTO messages(user_id,sender,text,created_at) VALUES(?,?,?,?)",
                     (uid, "bot", engine.CRISIS_REPLY, ts))
        conn.execute("INSERT INTO warnings(user_id,kind,detail,created_at) VALUES(?,?,?,?)",
                     (uid, "crisis", "You shared something that sounded very serious. Please use the helplines.", ts))
        conn.commit()
        return jsonify(crisis=True, reply=engine.CRISIS_REPLY)

    det = engine.detect(text, rating)
    aid = conn.execute("INSERT INTO assessments(user_id,message_id,category,confidence,stress_level,created_at) "
                       "VALUES(?,?,?,?,?,?)", (uid, mid, det["category"], det["confidence"], det["stress_level"], ts)).lastrowid

    new_warnings = evaluate_warnings(uid)
    has_warning = bool(new_warnings) or conn.execute(
        "SELECT 1 FROM warnings WHERE user_id=? AND acknowledged=0", (uid,)).fetchone() is not None
    seen = [r[0] for r in conn.execute("SELECT rec_key FROM recommendations WHERE user_id=? AND created_at>=? "
                                       "ORDER BY id DESC", (uid, days_ago(14)))]
    cat_count = conn.execute("SELECT COUNT(*) FROM assessments WHERE user_id=? AND category=? AND created_at>=?",
                             (uid, det["category"], days_ago(14))).fetchone()[0]
    recs = engine.recommend(det["category"], seen, cat_count, has_warning)
    conn.executemany("INSERT INTO recommendations(user_id,assessment_id,rec_key,text,created_at) VALUES(?,?,?,?,?)",
                     [(uid, aid, k, t, ts) for k, t in recs])

    reply = engine.reply_text(det["category"])
    if det["category"] != "neutral":
        reply += " Here are a few things that might help:"
    conn.execute("INSERT INTO messages(user_id,sender,text,created_at) VALUES(?,?,?,?)",
                 (uid, "bot", reply + "\n- " + "\n- ".join(t for _, t in recs), ts))
    conn.commit()
    return jsonify(crisis=False, reply=reply, detection=det, recommendations=[t for _, t in recs],
                   warnings=[d for _, d in new_warnings], disclaimer=engine.DISCLAIMER)


def days_ago(n):
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d %H:%M:%S")


def evaluate_warnings(uid):
    """Run trend checks; store new warnings (max one per kind per 24h)."""
    conn = db()
    week = [r[0] for r in conn.execute("SELECT stress_level FROM assessments WHERE user_id=? AND created_at>=?",
                                       (uid, days_ago(7)))]
    recent = [r[0] for r in conn.execute("SELECT stress_level FROM assessments WHERE user_id=? "
                                         "ORDER BY created_at DESC, id DESC LIMIT 6", (uid,))][::-1]
    fresh = []
    for kind, detail in engine.check_warnings(week, recent):
        dup = conn.execute("SELECT 1 FROM warnings WHERE user_id=? AND kind=? AND created_at>=?",
                           (uid, kind, days_ago(1))).fetchone()
        if not dup:
            conn.execute("INSERT INTO warnings(user_id,kind,detail,created_at) VALUES(?,?,?,?)", (uid, kind, detail, now()))
            fresh.append((kind, detail))
    return fresh


@app.get("/api/trends")
@login_required("employee")
def api_trends():
    uid, conn = g.user["id"], db()
    q = lambda sql: [dict(r) for r in conn.execute(sql, (uid,))]
    return jsonify(
        daily=q("SELECT date(created_at) AS period, ROUND(AVG(stress_level),2) AS avg, COUNT(*) AS n FROM assessments "
                "WHERE user_id=? AND created_at>=date('now','localtime','-60 day') GROUP BY period ORDER BY period"),
        weekly=q("SELECT strftime('%Y-W%W', created_at) AS period, ROUND(AVG(stress_level),2) AS avg, COUNT(*) AS n "
                 "FROM assessments WHERE user_id=? GROUP BY period ORDER BY period"),
        monthly=q("SELECT strftime('%Y-%m', created_at) AS period, ROUND(AVG(stress_level),2) AS avg, COUNT(*) AS n "
                  "FROM assessments WHERE user_id=? GROUP BY period ORDER BY period"),
        categories=q("SELECT category, COUNT(*) AS n FROM assessments WHERE user_id=? GROUP BY category ORDER BY n DESC"),
        open_warnings=conn.execute("SELECT COUNT(*) FROM warnings WHERE user_id=? AND acknowledged=0", (uid,)).fetchone()[0],
        thresholds={"elevated_avg": engine.ELEVATED_AVG},
        summary=user_summary(uid),
    )


@app.get("/api/admin/stats")
@login_required("admin")
def api_admin_stats():
    """Aggregates ONLY. No message text, names or per-employee rows ever leave
    this endpoint, and groups smaller than MIN_GROUP employees are suppressed."""
    conn = db()
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
    rows = lambda sql, *a: [dict(r) for r in conn.execute(sql, a)]
    return jsonify(
        employees=one("SELECT COUNT(*) FROM users WHERE role='employee'"),
        active_30d=one("SELECT COUNT(DISTINCT user_id) FROM assessments WHERE created_at>=?", days_ago(30)),
        assessments=one("SELECT COUNT(*) FROM assessments"),
        avg_stress_30d=one("SELECT ROUND(AVG(stress_level),2) FROM assessments WHERE created_at>=?", days_ago(30)),
        employees_with_open_warnings=(lambda n: n if n >= MIN_GROUP else None)(
            one("SELECT COUNT(DISTINCT user_id) FROM warnings WHERE acknowledged=0")),
        categories=rows("SELECT category, COUNT(*) AS n FROM assessments GROUP BY category "
                        "HAVING COUNT(DISTINCT user_id) >= ? ORDER BY n DESC", MIN_GROUP),
        weekly=rows("SELECT strftime('%Y-W%W', created_at) AS period, ROUND(AVG(stress_level),2) AS avg "
                    "FROM assessments GROUP BY period HAVING COUNT(DISTINCT user_id) >= ? ORDER BY period", MIN_GROUP),
        departments=rows("SELECT u.department AS department, ROUND(AVG(a.stress_level),2) AS avg "
                         "FROM assessments a JOIN users u ON u.id=a.user_id WHERE u.department<>'' "
                         "GROUP BY u.department HAVING COUNT(DISTINCT a.user_id) >= ? ORDER BY avg DESC", MIN_GROUP),
    )


init_db()
if HOSTED:  # fresh /tmp on every cold start, so rebuild the demo accounts
    import seed
    seed.seed(demo=True)

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
