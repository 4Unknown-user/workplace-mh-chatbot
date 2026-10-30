"""End-to-end checks. Run:  python test_app.py   (needs model/stress_model.joblib)"""
import os
import re
import tempfile

os.environ["DATABASE"] = os.path.join(tempfile.mkdtemp(), "test.db")

import engine  # noqa: E402
from app import app  # noqa: E402

app.config["TESTING"] = True


def csrf(client, path):
    return re.search(r'name="csrf" value="([^"]+)"', client.get(path).get_data(as_text=True)).group(1)


def register_login(client, email):
    t = csrf(client, "/register")
    client.post("/register", data={"csrf": t, "name": "T", "email": email, "password": "password123"})
    t = csrf(client, "/login")
    assert client.post("/login", data={"csrf": t, "email": email, "password": "password123"}).status_code == 302
    # login rotates the session (and its CSRF token); read the new one
    return re.search(r'name="csrf" content="([^"]+)"', client.get("/chat").get_data(as_text=True)).group(1)


def say(client, token, text, rating=None):
    return client.post("/api/chat", json={"message": text, "self_rating": rating}, headers={"X-CSRF": token}).get_json()


def main():
    # --- engine unit checks ---
    assert engine.detect("My manager micromanages me and shouts at me")["category"] == "management"
    assert engine.detect("the deadline is tomorrow and I'm running out of time")["category"] == "deadline"
    assert engine.is_crisis("I want to end it all") and not engine.is_crisis("I want to end this meeting")
    assert engine.check_warnings([8, 8, 9], [5, 6, 7, 8, 9])  # elevated + rising
    assert engine.check_warnings([2, 3, 2], [2, 3, 2, 3]) == []
    recs = engine.recommend("workload", seen_keys=list(engine.RECS["workload"])[:3], category_count_14d=0, has_warning=False)
    assert all(k not in list(engine.RECS["workload"])[:3] for k, _ in recs), "should prefer unseen suggestions"

    from datetime import date
    s = engine.summary([("2026-01-03 20:00:00", 8, "workload"), ("2026-01-04 10:00:00", 6, "workload"),
                        ("2026-01-05 10:00:00", 4, "neutral")], today=date(2026, 1, 5))
    assert s["streak"] == 3 and s["week_avg"] == 6.0 and s["after_hours"] == 2 and s["top_stressor"] == "Workload Stress"
    assert engine.summary([("2026-01-01 10:00:00", 5, "neutral")], today=date(2026, 1, 5))["streak"] == 0

    c = app.test_client()
    assert c.get("/chat").status_code == 302  # login required
    tok = register_login(c, "e1@test.local")
    assert c.post("/api/chat", json={"message": "hi"}).status_code == 400  # missing CSRF rejected

    r = say(c, tok, "I have way too many tasks and I'm overloaded", 9)
    assert r["detection"]["category"] == "workload" and 1 <= r["detection"]["stress_level"] <= 10
    assert len(r["recommendations"]) >= 3

    # repeated workload messages -> no repeated suggestions until the pool runs out, recurring tip appears
    r2 = say(c, tok, "my workload is crushing and the backlog keeps growing", 9)
    assert not set(r["recommendations"][:3]) & set(r2["recommendations"][:3])
    r3 = say(c, tok, "I'm swamped with work, too many tasks again", 10)
    assert any("several times" in x for x in r3["recommendations"])
    say(c, tok, "I'm buried under work and can't cope", 10)
    t = c.get("/api/trends").get_json()
    assert t["open_warnings"] >= 1 and t["daily"]

    crisis = say(c, tok, "I don't want to live anymore")
    assert crisis["crisis"] and "14416" in crisis["reply"]

    # --- privacy: employee cannot reach admin; admin cannot read chats ---
    assert c.get("/api/admin/stats").status_code == 403
    from werkzeug.security import generate_password_hash
    with app.app_context():
        from app import db
        db().execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES('A','a@t.l',?,'admin','x')",
                     (generate_password_hash("password123"),))
        db().commit()
    a = app.test_client()
    t = csrf(a, "/login")
    a.post("/login", data={"csrf": t, "email": "a@t.l", "password": "password123"})
    assert a.get("/chat").status_code == 403 and a.get("/history").status_code == 403
    stats = a.get("/api/admin/stats").get_json()
    assert stats["categories"] == []  # only 1 employee -> suppressed by k-anonymity
    assert "overloaded" not in str(stats)
    print("all tests passed")


if __name__ == "__main__":
    main()
