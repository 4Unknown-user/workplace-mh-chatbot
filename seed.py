"""Create the admin account and (optionally) demo employees with 45 days of history.

    python seed.py            # admin only
    python seed.py --demo     # admin + 6 demo employees with history (for presentations)

Demo logins (test data only):  admin@mindwork.local / Admin@1234
                               asha@demo.local ... / Demo@1234
"""
import csv
import random
import sys
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app import BASE, app, db, now

DEMO = [("Asha", "Engineering", "rising"), ("Rahul", "Engineering", "steady"), ("Meera", "Engineering", "falling"),
        ("Karan", "Sales", "steady"), ("Neha", "Sales", "rising"), ("Vikram", "Sales", "falling")]


def add_user(name, email, pw, role="employee", dept=""):
    conn = db()
    row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if row:
        return row[0], False
    uid = conn.execute("INSERT INTO users(name,email,department,password_hash,role,created_at) VALUES(?,?,?,?,?,?)",
                       (name, email, dept, generate_password_hash(pw), role, now())).lastrowid
    return uid, True


def seed(demo):
    random.seed(1)
    with app.app_context():
        add_user("Admin", "admin@mindwork.local", "Admin@1234", role="admin")
        if demo:
            with (BASE / "dataset" / "workplace_stress.csv").open(encoding="utf-8") as f:
                samples = {}
                for r in csv.DictReader(f):
                    samples.setdefault(r["label"], []).append(r["text"])
            cats = [c for c in samples if c != "neutral"]
            for name, dept, shape in DEMO:
                uid, created = add_user(name, f"{name.lower()}@demo.local", "Demo@1234", dept=dept)
                if not created:
                    continue
                favourite = random.sample(cats, 2)  # each person has recurring stressors
                for day in range(45, 0, -1):
                    if random.random() < 0.35:
                        continue
                    t = 1 - day / 45  # 0 -> 1 over the period
                    base = {"rising": 3 + 6 * t, "falling": 8 - 5 * t, "steady": 5}[shape]
                    level = max(1, min(10, round(base + random.uniform(-1.5, 1.5))))
                    cat = "neutral" if level <= 3 else random.choice(favourite + [random.choice(cats)])
                    ts = (datetime.now() - timedelta(days=day, hours=random.randint(0, 8))).strftime("%Y-%m-%d %H:%M:%S")
                    conn = db()
                    mid = conn.execute("INSERT INTO messages(user_id,sender,text,created_at) VALUES(?,?,?,?)",
                                       (uid, "user", random.choice(samples[cat]), ts)).lastrowid
                    conn.execute("INSERT INTO assessments(user_id,message_id,category,confidence,stress_level,created_at)"
                                 " VALUES(?,?,?,?,?,?)", (uid, mid, cat, round(random.uniform(0.55, 0.95), 3), level, ts))
                if shape == "rising":
                    conn.execute("INSERT INTO warnings(user_id,kind,detail,created_at) VALUES(?,?,?,?)",
                                 (uid, "rising", "Your stress has risen steadily across recent check-ins.", now()))
        db().commit()


if __name__ == "__main__":
    seed("--demo" in sys.argv)
    print("Seeded. Admin: admin@mindwork.local / Admin@1234" + (" | demo employees: <name>@demo.local / Demo@1234"
                                                              if "--demo" in sys.argv else ""))
