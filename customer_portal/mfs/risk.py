import time

import numpy as np
from django.conf import settings
from django.db import transaction as db_transaction

from .audit import audit
from .features import FEATURE_NAMES, feature_vector, transaction_features
from .ml import load_model
from .models import FraudAlert, ModelPrediction, ModelVersion, ReviewCase, RiskAssessment, RiskFactor


def _rule_factors(tx, features):
    factors = []
    def add(code, label, points, evidence):
        factors.append({"code": code, "label": label, "contribution": points, "source": "RULE", "evidence": evidence})
    if features["amount_deviation"] >= 5:
        add("AMOUNT_DEVIATION", "Unusual transaction amount", 32, {"ratio_to_average": round(features["amount_deviation"], 2)})
    if features["velocity_10m"] >= 10:
        add("HIGH_VELOCITY", "High transaction velocity", 24, {"transactions_last_10_min": features["velocity_10m"]})
    if tx.device_changed:
        add("NEW_DEVICE", "New or changed device", 18, {"device_changed": True})
    if tx.location_changed:
        add("NEW_LOCATION", "New or changed location", 12, {"location_changed": True})
    if features["new_beneficiaries"] >= 3:
        add("NEW_BENEFICIARIES", "Multiple new beneficiaries", 10, {"count": features["new_beneficiaries"]})
    if features["failed_24h"] >= 3:
        add("RECENT_FAILURES", "Repeated failed transactions", 8, {"failed_24h": features["failed_24h"]})
    return factors


@db_transaction.atomic
def assess_transaction(tx):
    started = time.perf_counter()
    model_version = ModelVersion.objects.filter(organization=tx.organization, status=ModelVersion.STATUS_ACTIVE).order_by("-trained_at").first()
    if not model_version:
        raise RuntimeError("No active risk model. Run `python manage.py train_risk_model` first.")
    artifact = load_model(model_version)
    features = transaction_features(tx)
    vector = feature_vector(features)
    fraud_probability = float(artifact["classifier"].predict_proba(vector)[0][1])
    raw_anomaly = float(-artifact["anomaly"].decision_function(vector)[0])
    anomaly_score = float(np.clip((raw_anomaly + .1) / .5, 0, 1))
    rule_factors = _rule_factors(tx, features)
    rule_score = min(sum(item["contribution"] for item in rule_factors), 100) / 100
    score = round(100 * (.55 * fraud_probability + .25 * anomaly_score + .20 * rule_score))
    high = settings.MFS_HIGH_RISK_THRESHOLD
    medium = settings.MFS_MEDIUM_RISK_THRESHOLD
    level = "HIGH" if score >= high else "MEDIUM" if score >= medium else "LOW"
    decision = "REVIEW" if level == "HIGH" else "MONITOR" if level == "MEDIUM" else "ALLOW"

    pipeline = artifact["classifier"]
    scaled = pipeline.named_steps["scale"].transform(vector)[0]
    coefficients = pipeline.named_steps["classifier"].coef_[0]
    ml_contributions = sorted(zip(FEATURE_NAMES, scaled * coefficients), key=lambda pair: abs(pair[1]), reverse=True)[:3]
    model_factors = [
        {"code": f"ML_{name.upper()}", "label": f"Model signal: {name.replace('_', ' ')}", "contribution": round(float(value), 3),
         "source": "MODEL", "evidence": {"feature_value": round(float(features[name]), 4)}}
        for name, value in ml_contributions if value > 0
    ]
    explanation_items = sorted(rule_factors, key=lambda item: item["contribution"], reverse=True)
    if not explanation_items:
        explanation_items = model_factors
    explanation = "; ".join(item["label"] for item in explanation_items[:5]) or "No elevated risk factors detected."
    elapsed = round((time.perf_counter() - started) * 1000)

    assessment = RiskAssessment.objects.create(
        organization=tx.organization, transaction=tx, model_version=model_version, score=score,
        level=level, decision=decision, fraud_probability=fraud_probability, anomaly_score=anomaly_score,
        rule_score=rule_score, inference_duration_ms=elapsed, explanation=explanation,
    )
    for factor in rule_factors + model_factors:
        RiskFactor.objects.create(assessment=assessment, **factor)
    ModelPrediction.objects.create(
        organization=tx.organization, transaction=tx, model_version=model_version,
        probability=fraud_probability, predicted_label=fraud_probability >= .5,
        feature_values=features, feature_contributions={name: round(float(value), 4) for name, value in ml_contributions},
    )
    if level == "HIGH":
        alert = FraudAlert.objects.create(
            organization=tx.organization, assessment=assessment,
            title=f"High risk transaction {tx.external_id}",
        )
        ReviewCase.objects.create(organization=tx.organization, alert=alert, priority="HIGH")
    audit("risk.assessed", organization=tx.organization, target=assessment, correlation_id=tx.correlation_id,
          metadata={"transaction_id": tx.external_id, "score": score, "level": level, "model_version": model_version.version})
    return assessment
