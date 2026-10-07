import json
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from django.utils import timezone
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_NAMES
from .models import ModelVersion


def synthetic_dataset(rows=8000, seed=42):
    rng = np.random.default_rng(seed)
    amount = rng.lognormal(8.0, 1.2, rows)
    average = rng.lognormal(7.8, 0.8, rows)
    hour = rng.integers(0, 24, rows)
    X = np.column_stack([
        np.log1p(amount), amount / np.maximum(average, 1), rng.poisson(2.5, rows),
        rng.poisson(0.4, rows), rng.binomial(1, .08, rows), rng.binomial(1, .06, rows),
        np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24),
        rng.beta(1.4, 8, rows), rng.beta(1.3, 9, rows), rng.poisson(.6, rows),
    ])
    logits = (
        -7.0 + 0.32 * X[:, 0] + 0.48 * np.clip(X[:, 1] - 1, 0, 12)
        + 0.22 * X[:, 2] + 0.5 * X[:, 3] + 1.0 * X[:, 4] + .8 * X[:, 5]
        + 2.0 * X[:, 8] + 1.7 * X[:, 9] + .3 * X[:, 10]
    )
    probability = 1 / (1 + np.exp(-np.clip(logits, -20, 20)))
    labels = rng.binomial(1, probability)
    return X, labels


def train_model(organization, rows=8000, seed=42):
    X, y = synthetic_dataset(rows=rows, seed=seed)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=.25, random_state=seed, stratify=y)
    classifier = Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed)),
    ])
    classifier.fit(X_train, y_train)
    anomaly = IsolationForest(n_estimators=150, contamination=.05, random_state=seed)
    anomaly.fit(X_train)
    probability = classifier.predict_proba(X_test)[:, 1]
    prediction = probability >= .5
    metrics = {
        "precision": float(precision_score(y_test, prediction, zero_division=0)),
        "recall": float(recall_score(y_test, prediction, zero_division=0)),
        "f1": float(f1_score(y_test, prediction, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probability)),
        "false_positive_rate": float(((prediction == 1) & (y_test == 0)).sum() / max((y_test == 0).sum(), 1)),
        "confusion_matrix": confusion_matrix(y_test, prediction).tolist(),
        "train_rows": int(len(X_train)), "test_rows": int(len(X_test)), "positive_rate": float(y.mean()),
    }
    version = timezone.now().strftime("v%Y%m%d%H%M%S")
    artifact_dir = Path(settings.MODEL_ARTIFACT_DIR)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"org-{organization.pk}-{version}.joblib"
    joblib.dump({"classifier": classifier, "anomaly": anomaly, "features": FEATURE_NAMES}, artifact_path)
    ModelVersion.objects.filter(organization=organization, status=ModelVersion.STATUS_ACTIVE).update(status=ModelVersion.STATUS_RETIRED)
    model = ModelVersion.objects.create(
        organization=organization, version=version, status=ModelVersion.STATUS_ACTIVE,
        artifact_path=str(artifact_path), dataset_version=f"synthetic-v1-seed-{seed}-rows-{rows}",
        feature_version="v1", parameters={"classifier": "logistic_regression", "anomaly": "isolation_forest", "seed": seed},
        metrics=metrics, trained_at=timezone.now(), is_synthetic=True,
    )
    return model


def load_model(model_version):
    path = Path(model_version.artifact_path)
    if not path.exists():
        raise FileNotFoundError(f"Model artifact is unavailable: {path.name}")
    return joblib.load(path)
