"""Train TF-IDF + Logistic Regression stress-category classifier.

Run:  python ml/train.py
Outputs: model/stress_model.joblib, model/metrics.txt, model/confusion_matrix.csv
"""
import csv
import sys
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine import preprocess  # noqa: E402  (shared so the pickled model can find it)

DATA = ROOT / "dataset" / "workplace_stress.csv"
OUT = ROOT / "model"
HELD_OUT_FROM = 9  # template index >= this goes to the test set


def build_pipeline():
    return Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=preprocess, ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=2000, C=5.0, class_weight="balanced")),
    ])


def main():
    with DATA.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    X = [r["text"] for r in rows]
    y = [r["label"] for r in rows]
    # Split by TEMPLATE, not by row: test sentences come from templates the model
    # never saw. A random row split leaks near-duplicates and reports ~100%.
    # Templates 9, 10, 11 of every class are held out (balanced, deterministic).
    test = [int(r["template_id"].rsplit("_", 1)[1]) >= HELD_OUT_FROM for r in rows]
    X_tr = [x for x, t in zip(X, test) if not t]
    y_tr = [c for c, t in zip(y, test) if not t]
    X_te = [x for x, t in zip(X, test) if t]
    y_te = [c for c, t in zip(y, test) if t]

    model = build_pipeline().fit(X_tr, y_tr)
    pred = model.predict(X_te)

    labels = [str(c) for c in model.classes_]
    report = classification_report(y_te, pred, digits=3)
    cm = confusion_matrix(y_te, pred, labels=labels)

    OUT.mkdir(exist_ok=True)
    # Metrics above come from the held-out split; the deployed model uses all data.
    joblib.dump(build_pipeline().fit(X, y), OUT / "stress_model.joblib")
    summary = (f"Samples: {len(X)}  train={len(X_tr)}  test={len(X_te)}\n"
               f"Accuracy: {accuracy_score(y_te, pred):.3f}\n\n{report}")
    (OUT / "metrics.txt").write_text(summary, encoding="utf-8")
    with (OUT / "confusion_matrix.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["true\\pred"] + labels)
        for lab, row in zip(labels, cm):
            w.writerow([lab] + [int(v) for v in row])
    print(summary)
    print("Confusion matrix (rows=true, cols=pred):", labels)
    for lab, row in zip(labels, cm):
        print(f"{lab:>15}", row)


if __name__ == "__main__":
    main()
