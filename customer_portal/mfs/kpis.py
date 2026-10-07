from django.db.models import Avg, DurationField, ExpressionWrapper, F, Sum
from django.utils import timezone

from .models import BusinessKPISnapshot, FraudAlert, ReviewDecision, RiskAssessment, Transaction


def calculate_business_kpis(organization, *, period_start=None, period_end=None):
    period_end = period_end or timezone.now()
    period_start = period_start or period_end - timezone.timedelta(days=30)
    transactions = Transaction.objects.filter(
        organization=organization, created_at__gte=period_start, created_at__lte=period_end
    )
    assessments = RiskAssessment.objects.filter(
        organization=organization, created_at__gte=period_start, created_at__lte=period_end
    )
    decisions = ReviewDecision.objects.filter(
        organization=organization, created_at__gte=period_start, created_at__lte=period_end
    )
    total = transactions.count()
    scored = transactions.filter(risk_assessments__isnull=False).distinct().count()
    high_risk = assessments.filter(level="HIGH").count()
    reviewed = decisions.values("review_case_id").distinct().count()
    confirmed = decisions.filter(decision=ReviewDecision.DECISION_REJECT)
    false_positive = decisions.filter(decision=ReviewDecision.DECISION_APPROVE).count()
    escalated = decisions.filter(decision=ReviewDecision.DECISION_ESCALATE).count()
    detection_duration = ExpressionWrapper(F("created_at") - F("transaction__created_at"), output_field=DurationField())
    review_duration = ExpressionWrapper(F("created_at") - F("review_case__opened_at"), output_field=DurationField())
    avg_detection = assessments.annotate(duration=detection_duration).aggregate(value=Avg("duration"))["value"]
    avg_review = decisions.annotate(duration=review_duration).aggregate(value=Avg("duration"))["value"]
    confirmed_value = confirmed.aggregate(value=Sum("review_case__alert__assessment__transaction__amount"))["value"] or 0
    active_alerts = FraudAlert.objects.filter(
        organization=organization, created_at__gte=period_start,
        status__in=[FraudAlert.STATUS_NEW, FraudAlert.STATUS_UNDER_REVIEW, FraudAlert.STATUS_ESCALATED],
    ).count()
    resolved = FraudAlert.objects.filter(
        organization=organization, created_at__gte=period_start,
        status__in=[FraudAlert.STATUS_CONFIRMED_RISK, FraudAlert.STATUS_FALSE_POSITIVE, FraudAlert.STATUS_RESOLVED],
    ).count()
    synthetic = transactions.filter(source__startswith="synthetic").exists() or transactions.filter(source="demo-script").exists()
    decision_count = decisions.count()
    return {
        "period_start": period_start.isoformat(), "period_end": period_end.isoformat(),
        "transactions_total": total, "transactions_scored": scored,
        "transactions_scored_pct": round(scored / max(total, 1) * 100, 2),
        "high_risk_detected": high_risk, "high_risk_reviewed": reviewed,
        "review_completion_pct": round(reviewed / max(high_risk, 1) * 100, 2),
        "average_detection_latency_ms": round(avg_detection.total_seconds() * 1000, 2) if avg_detection else None,
        "average_review_time_seconds": round(avg_review.total_seconds(), 2) if avg_review else None,
        "false_positives": false_positive,
        "false_positive_rate_pct": round(false_positive / max(decision_count, 1) * 100, 2),
        "confirmed_risk": confirmed.count(), "confirmed_risk_transaction_value": float(confirmed_value),
        "analyst_override_rate_pct": round(false_positive / max(decision_count, 1) * 100, 2),
        "escalated": escalated, "active_alerts": active_alerts, "alerts_resolved": resolved,
        "is_synthetic": synthetic,
    }


def create_business_kpi_snapshot(organization, *, days=30, generated_by="SYSTEM"):
    period_end = timezone.now()
    period_start = period_end - timezone.timedelta(days=days)
    metrics = calculate_business_kpis(organization, period_start=period_start, period_end=period_end)
    return BusinessKPISnapshot.objects.create(
        organization=organization, period_start=period_start, period_end=period_end,
        metrics=metrics, is_synthetic=metrics["is_synthetic"], generated_by=generated_by,
    )
