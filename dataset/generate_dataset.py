"""Generate a SYNTHETIC, EDUCATIONAL workplace-stress text dataset.

No public dataset labels workplace *stressor type* (most label stress yes/no,
e.g. Dreaddit), so we compose sentences from hand-written templates. Fixed seed
=> reproducible. Limitation (state it in the viva): templated text is easier
than real employee messages, so test accuracy here overestimates real-world
accuracy.

Run:  python dataset/generate_dataset.py   ->  dataset/workplace_stress.csv
"""
import csv
import random
from pathlib import Path

random.seed(42)

OPENERS = ["", "Honestly, ", "I don't know, ", "Lately ", "To be honest ", "Ugh, ", "These days ",
           "Not sure how to say this but ", "Hey, ", "So "]
CLOSERS = ["", ".", "...", " and it's wearing me down.", " and I can't switch off.",
           " I need some help.", " what should I do?", " it's getting to me.", " :("]

TEMPLATES = {
    "workload": [
        "I have way too many tasks on my plate",
        "my workload has doubled since {who} left",
        "I'm handling the work of {n} people",
        "there are so many tickets assigned to me I can't keep up",
        "every day more work gets dumped on me",
        "I'm drowning in {thing}",
        "the volume of work is impossible to finish in a normal day",
        "I keep getting extra projects without anything being taken off",
        "my to-do list never gets shorter no matter how hard I work",
        "I'm overloaded with {thing} and meetings",
        "I can't say no to more work and now I'm swamped",
        "too much work and too few people on the team",
    ],
    "deadline": [
        "the deadline for {proj} is tomorrow and I'm nowhere near done",
        "I'm panicking about the {proj} deadline",
        "the release date keeps getting pulled earlier",
        "I have {n} deadlines this week and they all overlap",
        "I keep worrying I'll miss the submission date",
        "the client wants {proj} delivered by Friday",
        "time is running out and the sprint ends {when}",
        "I'm anxious every time I look at the timeline for {proj}",
        "the due date is unrealistic and I'm scared of missing it",
        "countdown to the launch is giving me anxiety",
        "I lose sleep thinking about the deadline",
        "they moved the deadline up by a week without asking",
    ],
    "management": [
        "my manager micromanages everything I do",
        "my boss criticises me in front of everyone",
        "{boss} keeps changing priorities and blames me",
        "my supervisor expects replies at midnight",
        "my manager never gives clear instructions",
        "I feel pressured by {boss} to hit impossible targets",
        "my team lead takes credit for my work",
        "the management keeps pushing us harder every quarter",
        "my boss shouts when things go wrong",
        "my performance review felt unfair and my manager won't listen",
        "{boss} checks on me every hour",
        "leadership sets targets without asking us",
    ],
    "conflict": [
        "a colleague keeps undermining me in meetings",
        "I had a big argument with {who}",
        "my teammate refuses to cooperate on {proj}",
        "there is a lot of office politics and gossip about me",
        "a coworker is rude to me every day",
        "I feel excluded by my team",
        "my peer keeps blaming me for their mistakes",
        "there's tension between me and {who} and it's awkward",
        "people on my team talk behind my back",
        "a colleague dismisses every idea I bring up",
        "I'm in a constant conflict with another department",
        "someone at work is being hostile to me",
    ],
    "work_life": [
        "I haven't spent time with my family in weeks because of work",
        "I work every weekend and have no personal life",
        "I check emails at {when} even on holidays",
        "my job eats into all my evenings",
        "I missed my {event} because of a late meeting",
        "working from home means I never log off",
        "I have no time for exercise or hobbies anymore",
        "my partner says I'm always on my laptop",
        "I can't remember my last real day off",
        "work calls keep coming during dinner",
        "I'm always working late and my health is suffering",
        "there's no boundary between my job and my home",
    ],
    "job_insecurity": [
        "there are rumours of layoffs and I'm scared",
        "I'm afraid I'll lose my job",
        "the company announced restructuring and I might be cut",
        "my contract ends soon and nobody says if it'll be renewed",
        "they fired {n} people last week and I could be next",
        "I'm worried about my job security after the merger",
        "I feel replaceable and expect to be let go",
        "the project might be cancelled and my role with it",
        "I fear being put on a performance improvement plan",
        "the startup is running out of funding and I'm worried",
        "everyone is talking about downsizing",
        "I'm on probation and terrified of failing it",
    ],
    "low_motivation": [
        "I don't feel like doing anything at work anymore",
        "I've lost interest in my job",
        "my work feels meaningless",
        "I can't find the energy to start {thing}",
        "I'm bored and unmotivated every day",
        "nothing at work excites me like it used to",
        "I keep procrastinating and don't care about {proj}",
        "I feel stuck in the same role with no growth",
        "I drag myself to work every morning",
        "I don't see the point of my tasks",
        "I feel like I'm just going through the motions",
        "no recognition for my effort so why bother",
    ],
    "neutral": [
        "I had a pretty good day at work",
        "the meeting with {who} went well",
        "I finished {proj} on time and feel fine",
        "things at work are okay right now",
        "my team had a nice lunch together",
        "I just wanted to check in, all good today",
        "work is manageable this week",
        "I learned something new on {proj}",
        "my manager appreciated my work today",
        "feeling calm and productive",
        "nothing special, an ordinary day",
        "I'm looking forward to the weekend",
    ],
}

# Short class-specific clauses appended to ~70% of sentences. They carry the
# vocabulary employees actually use, so held-out templates are still learnable.
CLAUSES = {
    "workload": ["the backlog keeps growing", "I'm overloaded", "too many tasks", "the workload is crushing",
                 "I'm swamped with work", "extra assignments keep coming", "no one shares the load",
                 "I'm buried under work", "my task list is endless", "I'm stretched too thin"],
    "deadline": ["the deadline is so close", "I'm running out of time", "the due date is tomorrow",
                 "the timeline is impossible", "I'm racing the clock", "the submission is due soon",
                 "time pressure is huge", "the launch date is near", "I'm behind schedule", "the cutoff is today"],
    "management": ["my manager is pressuring me", "my boss is never satisfied", "my supervisor is breathing down my neck",
                   "the boss keeps micromanaging", "management demands too much", "my lead is so controlling",
                   "my manager keeps criticising me", "the boss won't listen", "my manager is unfair",
                   "pressure from my boss"],
    "conflict": ["my colleague is hostile", "my coworker keeps arguing", "the team is fighting",
                 "a teammate is undermining me", "office politics are toxic", "my colleague is rude",
                 "I'm clashing with a coworker", "there's drama on my team", "a peer keeps blaming me",
                 "my coworkers exclude me"],
    "work_life": ["I have no personal time", "my family barely sees me", "I work late every night",
                  "my weekends are gone", "I can't log off", "no time for myself", "I'm always online for work",
                  "my evenings belong to my job", "I skipped my holiday", "home and work have blurred"],
    "job_insecurity": ["layoffs are coming", "I might get fired", "my job could be cut", "they are downsizing",
                       "my position is at risk", "I could be laid off", "my contract may end",
                       "the company is cutting jobs", "I fear losing my job", "restructuring threatens my role"],
    "low_motivation": ["I feel unmotivated", "I've lost my drive", "I just don't care anymore", "work feels pointless",
                       "I have zero enthusiasm", "I feel disengaged", "I can't get myself started",
                       "I'm bored all the time", "nothing feels rewarding", "I've lost interest"],
    "neutral": ["all is well", "I'm feeling fine", "things are calm", "it's been a good week",
                "I'm doing okay", "work is pleasant", "no complaints today", "everything is on track",
                "I'm in a good mood", "the day went smoothly"],
}
LINKS = [" because ", " and ", " — ", ". Also ", ", plus ", ". "]

FILL = {
    "who": ["my colleague", "a senior dev", "Ravi", "my teammate", "the other analyst", "Priya"],
    "n": ["two", "three", "four", "5", "several"],
    "thing": ["emails", "reports", "bug fixes", "client requests", "documentation", "spreadsheets"],
    "proj": ["the project", "the report", "the presentation", "the app release", "the audit", "the proposal"],
    "when": ["midnight", "tomorrow", "11pm", "6am", "Friday"],
    "boss": ["My manager", "My boss", "The team lead", "My supervisor"],
    "event": ["kid's birthday", "friend's wedding", "doctor appointment", "family dinner"],
}

PER_TEMPLATE = 20  # 8 labels x 12 templates x 20 = 1920 rows


def fill(t):
    for k, v in FILL.items():
        while "{" + k + "}" in t:
            t = t.replace("{" + k + "}", random.choice(v), 1)
    return t


def main():
    rows = set()
    for label, temps in TEMPLATES.items():
        for ti, t in enumerate(temps):
            for _ in range(PER_TEMPLATE):
                body = fill(t)
                if random.random() < 0.7:
                    body += random.choice(LINKS) + random.choice(CLAUSES[label])
                s = (random.choice(OPENERS) + body + random.choice(CLOSERS)).strip()
                rows.add((s[0].upper() + s[1:], label, f"{label}_{ti}"))
    rows = sorted(rows)
    random.shuffle(rows)
    out = Path(__file__).with_name("workplace_stress.csv")
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text", "label", "template_id"])
        w.writerows(rows)
    print(f"wrote {len(rows)} unique rows -> {out}")


if __name__ == "__main__":
    main()
