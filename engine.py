"""Core logic, kept free of Flask so it can be unit-tested:
  1. detect()            workplace stress category + confidence + stress level
  2. check_warnings()    longitudinal trend analysis -> early warnings
  3. recommend()         history-aware personalised recommendations
"""
import random
import re
from pathlib import Path

import joblib

MODEL_PATH = Path(__file__).with_name("model") / "stress_model.joblib"
_model = None

LABELS = {
    "workload": "Workload Stress", "deadline": "Deadline Anxiety", "management": "Management Pressure",
    "conflict": "Workplace Conflict", "work_life": "Work-Life Imbalance", "job_insecurity": "Job Insecurity",
    "low_motivation": "Low Motivation", "neutral": "No significant stress",
}
BASE_LEVEL = {"workload": 6, "deadline": 6, "management": 6, "conflict": 6, "work_life": 5,
              "job_insecurity": 7, "low_motivation": 5, "neutral": 2}
INTENSIFIERS = re.compile(r"\b(can't|cannot|never|always|exhausted|burn(ed|t)? ?out|panic\w*|terrified|"
                          r"overwhelm\w*|breaking|crying|hopeless|desperate|unbearable|so much|too much)\b", re.I)

# Checked BEFORE the classifier. Deliberately broad: a false positive costs one
# extra helpline message, a false negative could cost much more.
CRISIS = re.compile(r"\b(kill (myself|me)|suicid\w*|end (my|it all)|take my (own )?life|self[- ]?harm|"
                    r"hurt myself|cut myself|want to die|better off dead|no reason to live|don't want to live)\b", re.I)

CRISIS_REPLY = (
    "I'm really sorry you're feeling this way, and I'm glad you told me. I'm an automated assistant and "
    "can't give you the support you deserve right now, but people can. Please reach out immediately:\n"
    "• India: Tele-MANAS 14416 or 1-800-891-4416 (24x7, free) · KIRAN 1800-599-0019\n"
    "• Emergency: 112 (India) / your local emergency number\n"
    "• Elsewhere: findahelpline.com lists free, confidential lines in your country\n"
    "If you can, contact someone you trust or your company's Employee Assistance Programme (EAP) now. "
    "You don't have to go through this alone."
)

DISCLAIMER = "I'm a supportive tool, not a clinician — I can't diagnose conditions or replace professional help."

EMPATHY = {
    "workload": ["That sounds like a heavy load to carry.", "Having more work than hours is genuinely exhausting.",
                 "It makes sense you feel stretched — that's a lot on one person."],
    "deadline": ["Deadline pressure can make everything feel urgent at once.", "That ticking-clock feeling is really stressful.",
                 "It's understandable to feel anxious with time running short."],
    "management": ["Pressure from above can feel hard to push back on.", "That kind of dynamic with a manager is draining.",
                   "It's tough when you don't feel supported by leadership."],
    "conflict": ["Friction with colleagues can make every day feel heavy.", "That sounds uncomfortable and isolating.",
                 "Conflicts at work are stressful, especially when they keep repeating."],
    "work_life": ["It sounds like work has crept into the rest of your life.", "Missing personal time adds up quickly.",
                  "You deserve time that belongs only to you."],
    "job_insecurity": ["Uncertainty about your job is one of the most stressful things at work.",
                       "Not knowing what's next is really hard.", "It's natural to worry when stability feels shaky."],
    "low_motivation": ["Feeling flat about work happens to many people, and it's worth paying attention to.",
                       "It's hard to push when the spark isn't there.", "Thanks for being honest about how disengaged you feel."],
    "neutral": ["Glad to hear things are okay.", "Thanks for checking in!", "Nice — it's good to notice the calmer days too."],
}

# key -> text. Keys let us remember what each employee has already seen.
RECS = {
    "workload": {
        "wl_triage": "List today's tasks and mark each Urgent/Important (Eisenhower matrix). Do only the top 3 first.",
        "wl_capacity": "Bring your task list to your manager and ask: 'Which of these should I deprioritise?'",
        "wl_batch": "Batch shallow work (emails, chats) into two fixed 30-minute slots instead of all day.",
        "wl_no": "Practise a polite decline: 'I can take this on if X moves to next week — which do you prefer?'",
        "wl_delegate": "Identify one recurring task someone else could own or that could be automated.",
        "wl_break": "Use 50/10 blocks: 50 minutes focused, 10 minutes away from the screen.",
    },
    "deadline": {
        "dl_chunk": "Break the deliverable into 30–60 minute chunks and schedule them backwards from the due date.",
        "dl_mvp": "Define the minimum acceptable version first; polish only if time remains.",
        "dl_early": "If the date is at risk, flag it early with a revised estimate — early warnings are respected, late surprises aren't.",
        "dl_breath": "Try box breathing (4s in, 4s hold, 4s out, 4s hold) for 2 minutes before starting.",
        "dl_buffer": "Next time, add a 20% buffer to your estimates for unknowns.",
        "dl_single": "Close all tabs and notifications for one 45-minute focus sprint on the hardest part.",
    },
    "management": {
        "mg_clarify": "After each instruction, reply with a short summary: 'So the priority is A, by Thursday — correct?'",
        "mg_1on1": "Request a regular 1:1 and bring two specific examples plus a proposed solution.",
        "mg_document": "Keep a private log of requests, dates and outcomes; it helps in reviews and discussions.",
        "mg_expect": "Ask your manager to agree on response-time expectations outside work hours.",
        "mg_feedback": "Frame feedback with 'When X happens, I find it harder to deliver Y. Could we try Z?'",
        "mg_hr": "If pressure turns into disrespect or unfair treatment, HR or a skip-level manager is a legitimate route.",
    },
    "conflict": {
        "cf_private": "Talk to the colleague privately and calmly, using 'I' statements rather than accusations.",
        "cf_pause": "Before replying to a heated message, wait 20 minutes and re-read your draft.",
        "cf_common": "Find one shared goal you both care about and start the conversation from there.",
        "cf_mediate": "If direct talk doesn't work, ask your manager or HR for a facilitated conversation.",
        "cf_ally": "Build connection with one supportive teammate — isolation makes conflict feel bigger.",
        "cf_facts": "Keep notes of incidents with dates and facts, in case you need to escalate.",
    },
    "work_life": {
        "wb_shutdown": "Create a 5-minute shutdown ritual: write tomorrow's top 3, close the laptop, say 'done'.",
        "wb_notif": "Turn off work notifications after a fixed hour and set an auto-reply for after-hours mail.",
        "wb_protect": "Block one evening a week in your calendar for something personal — treat it like a meeting.",
        "wb_move": "Schedule a 20-minute walk or exercise slot; physical activity is a strong stress buffer.",
        "wb_leave": "Check your leave balance and plan a real break, even a long weekend.",
        "wb_space": "If you work from home, keep work to one physical spot and leave it when done.",
    },
    "job_insecurity": {
        "ji_control": "Write two lists: what you can control (skills, network, savings) and what you can't. Act only on the first.",
        "ji_skills": "Pick one in-demand skill and spend 20 minutes a day on a free course.",
        "ji_update": "Refresh your CV/LinkedIn with recent achievements — it's useful regardless of what happens.",
        "ji_ask": "Ask your manager directly how your role fits upcoming plans; clarity often reduces anxiety.",
        "ji_network": "Reconnect with two former colleagues this week — just a friendly check-in.",
        "ji_finance": "Review a basic emergency budget; knowing your runway can ease worry.",
    },
    "low_motivation": {
        "lm_small": "Start with a 5-minute task you can finish — momentum often follows action.",
        "lm_meaning": "Write down who benefits from your work this week; reconnecting with impact helps.",
        "lm_growth": "Ask your manager about a stretch task or learning opportunity.",
        "lm_reward": "Pair a dull task with something pleasant (good music, a coffee afterwards).",
        "lm_wins": "Keep a 'done list' — note three things you completed at the end of each day.",
        "lm_rest": "Check your sleep and breaks; low motivation is sometimes plain exhaustion.",
    },
    "neutral": {
        "nt_gratitude": "Note one thing that went well today — it builds resilience for tougher days.",
        "nt_habit": "Good days are a great time to set up a healthy routine (walk, water, breaks).",
        "nt_connect": "Say thanks to a colleague who helped you recently.",
    },
}

RECURRING = {
    "workload": "Workload has come up several times recently. Consider a formal workload review with your manager.",
    "deadline": "Deadline stress keeps recurring — it may be worth discussing planning/estimation practices with your team.",
    "management": "This has been a repeated theme. Your organisation's HR or EAP can offer confidential guidance.",
    "conflict": "This conflict seems ongoing. A mediated conversation via HR is a reasonable next step.",
    "work_life": "The imbalance looks persistent. Talk to your manager about workload or flexible hours.",
    "job_insecurity": "This worry keeps returning. A career counsellor or your EAP can help you plan.",
    "low_motivation": "Low motivation has persisted for a while. If it spreads beyond work, consider talking to a counsellor.",
}


def preprocess(text):
    """Lowercase, keep letters/apostrophes, collapse spaces. Negations like
    "don't" are kept on purpose. Used inside the TF-IDF pipeline (ml/train.py)."""
    text = re.sub(r"[^a-z' ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def get_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


def is_crisis(text):
    return bool(CRISIS.search(text))


def detect(text, self_rating=None):
    """Return dict(category, label, confidence, stress_level 1-10)."""
    model = get_model()
    probs = model.predict_proba([text])[0]
    i = probs.argmax()
    cat = model.classes_[i]
    level = BASE_LEVEL[cat] + min(3, len(INTENSIFIERS.findall(text))) if cat != "neutral" else BASE_LEVEL[cat]
    if self_rating:  # blend with the employee's own 1-10 rating
        level = round(0.5 * level + 0.5 * int(self_rating))
    return {"category": cat, "label": LABELS[cat], "confidence": round(float(probs[i]), 3),
            "stress_level": max(1, min(10, level))}


def slope(ys):
    """Least-squares slope of ys against 0..n-1 (stdlib, no numpy needed)."""
    n = len(ys)
    if n < 2:
        return 0.0
    mx, my = (n - 1) / 2, sum(ys) / n
    den = sum((x - mx) ** 2 for x in range(n))
    return sum((x - mx) * (y - my) for x, y in enumerate(ys)) / den


ELEVATED_AVG = 7.0   # 7-day average at/above this -> warning
RISING_SLOPE = 0.5   # +0.5 level per assessment over the last 6 -> warning


def check_warnings(levels_last_7_days, recent_levels):
    """levels_last_7_days: stress levels in the past 7 days.
    recent_levels: the last <=6 levels, oldest first. Returns [(kind, detail)]."""
    out = []
    if len(levels_last_7_days) >= 3:
        avg = sum(levels_last_7_days) / len(levels_last_7_days)
        if avg >= ELEVATED_AVG:
            out.append(("elevated", f"Your average stress over the last 7 days is {avg:.1f}/10."))
    if len(recent_levels) >= 4:
        s = slope(recent_levels)
        if s >= RISING_SLOPE and recent_levels[-1] >= 6:
            out.append(("rising", f"Your stress has risen steadily across your last {len(recent_levels)} check-ins."))
    if len(recent_levels) >= 3 and all(l >= 8 for l in recent_levels[-3:]):
        out.append(("sustained_high", "Your last 3 check-ins were all 8/10 or higher."))
    return out


def recommend(category, seen_keys, category_count_14d, has_warning, k=3):
    """seen_keys: rec keys shown to this employee recently, most recent first.
    Unseen suggestions are preferred; if all were seen, the least recently seen
    are reused. Returns [(key, text)]."""
    pool = RECS[category]
    unseen = [key for key in pool if key not in seen_keys]
    random.shuffle(unseen)
    stale = sorted((key for key in pool if key in seen_keys), key=seen_keys.index, reverse=True)
    picks = [(key, pool[key]) for key in (unseen + stale)[:k]]
    if category in RECURRING and category_count_14d >= 3:
        picks.append((f"recurring_{category}", RECURRING[category]))
    if has_warning and category != "neutral":
        picks.append(("pro_help", "Because your recent stress has been high, talking to a counsellor, "
                                  "your EAP, or a doctor could really help. Reaching out is a sign of strength."))
    return picks


def reply_text(category):
    return random.choice(EMPATHY[category])
