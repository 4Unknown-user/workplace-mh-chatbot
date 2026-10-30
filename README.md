# MindWork — AI-Powered Mental Health Chatbot for Workplace

B.Tech CSE-AIML in-house project. A Flask web app where employees chat about work stress. The app:

1. **Detects the workplace stressor** with TF-IDF + Logistic Regression and shows the category, a confidence score and a 1–10 stress level.
2. **Tracks stress over time** in SQLite: daily, weekly and monthly averages, Chart.js trend charts and **early warnings**.
3. **Gives personalised recommendations** per stressor. These are history-aware: they avoid repeats, add an escalation tip for stressors that keep coming back, and suggest professional help while warnings are active.

> MindWork is a self-help and educational tool. It does **not** diagnose and does **not** replace professional care. Crisis messages bypass the ML model and return helplines right away.

## Architecture

```
Browser (Bootstrap + JS + Chart.js)
   │  HTML pages + JSON (fetch, CSRF header)
Flask app.py ── auth, sessions, CSRF, role checks, SQL
   │                     │
engine.py                SQLite (instance/wellbeing.db)
 ├ is_crisis()  regex safety net (runs first)
 ├ detect()     model/stress_model.joblib → category, confidence, level
 ├ check_warnings()  7-day avg ≥7 · rising slope · 3× ≥8
 └ recommend()  per-category pools, unseen-first, recurring + pro-help tips
ml/train.py → trains on dataset/workplace_stress.csv → model/
```

## Folder structure

```
workplace-mh-chatbot/
├── app.py                 Flask routes, DB schema, APIs
├── engine.py              detection, warnings, recommendations, safety
├── seed.py                admin account (+ --demo employees with 45 days of history)
├── test_app.py            end-to-end tests
├── requirements.txt
├── dataset/
│   ├── generate_dataset.py
│   └── workplace_stress.csv   (generated, 1,903 rows, 8 labels)
├── ml/train.py
├── model/                 stress_model.joblib, metrics.txt, confusion_matrix.csv
├── templates/             base, index, register, login, chat, history, dashboard, warnings, admin
├── static/                style.css, chat.js, charts.js
└── instance/wellbeing.db  (created on first run)
```

## Database (SQLite, foreign keys ON, cascading deletes)

| Table | Key columns |
|---|---|
| users | id, name, email UNIQUE, department, password_hash (Werkzeug PBKDF2/scrypt), role CHECK employee/admin |
| messages | user_id → users, sender user/bot, text |
| assessments | user_id → users, message_id → messages, category, confidence, stress_level CHECK 1–10 |
| recommendations | user_id → users, assessment_id → assessments, rec_key, text |
| warnings | user_id → users, kind (elevated / rising / sustained_high / crisis), detail, acknowledged |

## Install and run (Windows / macOS / Linux, Python 3.10+)

```bash
cd workplace-mh-chatbot
```

```bash
python -m venv venv
```

Activate it with `venv\Scripts\activate` on Windows or `source venv/bin/activate` on macOS/Linux. Then:

```bash
pip install -r requirements.txt
```

```bash
python dataset/generate_dataset.py
```

```bash
python ml/train.py
```

```bash
python seed.py --demo
```

```bash
python app.py
```

Open http://127.0.0.1:5000.

| Role | Login (demo/test data only) |
|---|---|
| Admin | admin@mindwork.local / Admin@1234 |
| Employees | asha@, rahul@, meera@, karan@, neha@, vikram@ `demo.local` / Demo@1234 |

Asha and Neha have a *rising* trend, which triggers early warnings. You can also register a new employee. For a real deployment, set a fixed `SECRET_KEY` environment variable and change the admin password.

## Dataset and model results

There's no public dataset labelled by *workplace stressor type*. Dreaddit, for example, only labels stress yes/no. So `generate_dataset.py` builds a **documented synthetic educational dataset**: 8 labels × 12 hand-written templates, plus slot fillers and a per-class phrase bank, with a fixed seed.

**Evaluation is honest.** Templates 9–11 of every class are **held out completely**, so the test set uses sentence structures the model never saw. A random row split scored 100% only because near-duplicates leaked between train and test. That number is meaningless, so it isn't reported.

Held-out results (`model/metrics.txt`):

| | Precision | Recall | F1 |
|---|---|---|---|
| **Accuracy** | | | **0.813** |
| Macro avg | 0.821 | 0.812 | 0.810 |

The weakest classes are workload↔conflict and job_insecurity→deadline (see `model/confusion_matrix.csv`). Real employee text will score lower. Collecting and labelling real, consented messages is the main future-work item.

The deployed model is retrained on all rows after evaluation.

## Testing

```bash
python test_app.py
```

The tests cover:
- Classifier sanity checks
- Crisis detection, including the false-positive case "end this meeting"
- Warning rules
- No-repeat recommendations
- Login required, CSRF rejection, the full chat flow, warnings and the recurring tip
- Crisis reply with helplines
- Employee blocked from admin, admin blocked from chats and history
- k-anonymity suppression

**Manual demo script for the viva:**
1. Log in as asha → Chat → "My manager keeps adding tasks and the deadline is Friday" with the slider at 9. You'll see the category, confidence, level and recommendations.
2. Send another workload message. The suggestions don't repeat, and after 3 workload messages in 14 days the recurring tip appears.
3. Open Trends: daily, weekly and monthly charts with the threshold line.
4. Open Alerts: the early warnings.
5. Type "I don't want to live anymore": you get the crisis response with helplines, and no classification.
6. Log in as admin. Only aggregates are shown. Try `/history` and you get 403.

## Privacy and safety design
- Admin endpoints run aggregate SQL only. They never select message text, names or per-employee rows.
- Groups with fewer than 3 employees are hidden (k-anonymity).
- Admins can't open employee pages (403). Employees can't open admin pages.
- Passwords are hashed with Werkzeug. CSRF tokens are checked on every POST, and the session rotates on login. There are no open redirects, and user text is rendered with `textContent` / Jinja autoescape to prevent XSS.
- The crisis regex runs **before** the model and is deliberately broad. Helplines: India Tele-MANAS 14416, KIRAN 1800-599-0019, emergency 112, findahelpline.com.

## Limitations / future work
- Synthetic training data. Next steps: real labelled data, multi-label stressors (one message often has two), and calibrated confidence.
- The rule-based stress level (category base + intensifier words, blended 50/50 with the optional self-rating) is a heuristic, not a validated psychometric scale such as PSS-10.
- No email or push notifications: warnings show in-app only.
