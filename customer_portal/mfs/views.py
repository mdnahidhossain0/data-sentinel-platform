import json

import requests
from django.contrib import messages
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .assistant import answer_question
from .audit import audit
from .auth import ROLE_ADMIN, ROLE_ANALYST, ROLE_REVIEWER, ROLE_VIEWER, require_roles
from .connectors import discover_schema, encrypt_password
from .forms import AssistantForm, DataSourceForm, ReviewDecisionForm
from .kpis import calculate_business_kpis
from .models import (
    DataPipeline, DataQualityMetric, DataSource, FraudAlert, IngestionAPIKey, ModelVersion,
    ReviewCase, ReviewDecision, RiskAssessment, Transaction, TransactionEvent, TransactionLabel,
)
from .services import record_review_decision


ALL_ROLES = (ROLE_ADMIN, ROLE_ANALYST, ROLE_REVIEWER, ROLE_VIEWER)


@require_roles(*ALL_ROLES)
def dashboard(request):
    org = request.user.organization
    txs = Transaction.objects.filter(organization=org)
    assessments = RiskAssessment.objects.filter(organization=org)
    reviewed = ReviewDecision.objects.filter(organization=org)
    false_positives = reviewed.filter(review_case__alert__status=FraudAlert.STATUS_FALSE_POSITIVE).count()
    context = {
        "total_transactions": txs.count(), "total_value": txs.aggregate(value=Sum("amount"))["value"] or 0,
        "successful": txs.filter(status="SUCCESS").count(), "failed": txs.filter(status="FAILED").count(),
        "high_risk": assessments.filter(level="HIGH").count(), "average_risk": assessments.aggregate(value=Avg("score"))["value"] or 0,
        "active_alerts": FraudAlert.objects.filter(organization=org, status__in=["NEW", "UNDER_REVIEW", "ESCALATED"]).count(),
        "risk_counts": {level: assessments.filter(level=level).count() for level in ("LOW", "MEDIUM", "HIGH")},
        "false_positive_rate": (false_positives / reviewed.count() * 100) if reviewed.exists() else 0,
        "reviewed": reviewed.count(), "pipelines": DataPipeline.objects.filter(organization=org).order_by("name"),
        "quality": DataQualityMetric.objects.filter(organization=org).order_by("-measured_at")[:6],
        "latest_alerts": FraudAlert.objects.filter(organization=org).select_related("assessment__transaction")[:6],
        "model": ModelVersion.objects.filter(organization=org, status="ACTIVE").first(),
        "events_processed": TransactionEvent.objects.filter(organization=org, status="PROCESSED").count(),
        "events_failed": TransactionEvent.objects.filter(organization=org, status="FAILED").count(),
        "business_kpis": calculate_business_kpis(org),
    }
    return render(request, "mfs/dashboard.html", context)


@require_roles(*ALL_ROLES)
def business_kpis(request):
    org = request.user.organization
    try:
        days = min(max(int(request.GET.get("days", 30)), 1), 365)
    except ValueError:
        days = 30
    end = timezone.now()
    metrics = calculate_business_kpis(org, period_start=end - timezone.timedelta(days=days), period_end=end)
    snapshots = org.businesskpisnapshot_set.order_by("-period_end")[:12]
    return render(request, "mfs/business_kpis.html", {"metrics": metrics, "days": days, "snapshots": snapshots})


@require_roles(*ALL_ROLES)
def transaction_list(request):
    qs = Transaction.objects.filter(organization=request.user.organization).select_related("customer")
    level = request.GET.get("risk")
    if level in {"LOW", "MEDIUM", "HIGH"}: qs = qs.filter(risk_assessments__level=level)
    return render(request, "mfs/transaction_list.html", {"transactions": qs[:200], "risk_filter": level})


@require_roles(*ALL_ROLES)
def transaction_detail(request, pk):
    tx = get_object_or_404(Transaction.objects.select_related("customer"), pk=pk, organization=request.user.organization)
    assessment = tx.risk_assessments.prefetch_related("factors").first()
    return render(request, "mfs/transaction_detail.html", {"transaction": tx, "assessment": assessment})


@require_roles(*ALL_ROLES)
def alert_list(request):
    alerts = FraudAlert.objects.filter(organization=request.user.organization).select_related("assessment__transaction", "assigned_to")[:200]
    return render(request, "mfs/alert_list.html", {"alerts": alerts})


@require_roles(ROLE_ADMIN, ROLE_ANALYST, ROLE_REVIEWER)
def review_queue(request):
    cases = ReviewCase.objects.filter(organization=request.user.organization).select_related("alert__assessment__transaction", "assigned_to")
    return render(request, "mfs/review_queue.html", {"cases": cases})


@require_roles(ROLE_ADMIN, ROLE_ANALYST, ROLE_REVIEWER)
def review_detail(request, pk):
    case = get_object_or_404(ReviewCase.objects.select_related("alert__assessment__transaction__customer"), pk=pk, organization=request.user.organization)
    form = ReviewDecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        record_review_decision(case, request.user, form.cleaned_data["decision"], form.cleaned_data["reason"], form.cleaned_data["comments"])
        messages.success(request, "Review decision recorded and audit trail updated.")
        return redirect("mfs:review_detail", pk=case.pk)
    return render(request, "mfs/review_detail.html", {"case": case, "form": form})


@require_roles(ROLE_ADMIN, ROLE_ANALYST)
def data_sources(request):
    return render(request, "mfs/data_sources.html", {"sources": DataSource.objects.filter(organization=request.user.organization)})


@require_roles(ROLE_ADMIN)
def data_source_create(request):
    form = DataSourceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        source = form.save(commit=False); source.organization = request.user.organization
        source.encrypted_password = encrypt_password(form.cleaned_data["password"]); source.save()
        audit("data_source.created", organization=request.user.organization, actor=request.user, target=source, metadata={"engine": source.engine})
        messages.success(request, "Data source saved with encrypted credentials.")
        return redirect("mfs:data_sources")
    return render(request, "mfs/form.html", {"form": form, "title": "Connect MFS database", "submit": "Save source"})


@require_roles(ROLE_ADMIN, ROLE_ANALYST)
def discover_data_source(request, pk):
    source = get_object_or_404(DataSource, pk=pk, organization=request.user.organization)
    if request.method == "POST":
        try:
            version, changed = discover_schema(source)
            messages.success(request, f"Schema v{version.version} registered ({'changed' if changed else 'unchanged'}).")
        except Exception as error:
            source.status = "ERROR"; source.save(update_fields=["status", "updated_at"])
            messages.error(request, f"Schema discovery failed: {error}")
    return redirect("mfs:schema_detail", pk=source.pk)


@require_roles(*ALL_ROLES)
def schema_detail(request, pk):
    source = get_object_or_404(DataSource, pk=pk, organization=request.user.organization)
    version = source.schema_versions.prefetch_related("tables__columns").first()
    return render(request, "mfs/schema_detail.html", {"source": source, "version": version})


@require_roles(*ALL_ROLES)
def model_monitor(request):
    models = ModelVersion.objects.filter(organization=request.user.organization).order_by("-trained_at")
    labels = TransactionLabel.objects.filter(organization=request.user.organization).select_related("transaction")
    tp = fp = tn = fn = 0
    for label in labels:
        assessment = label.transaction.risk_assessments.first()
        if not assessment:
            continue
        predicted = assessment.level == "HIGH"
        if predicted and label.is_fraud: tp += 1
        elif predicted and not label.is_fraud: fp += 1
        elif not predicted and label.is_fraud: fn += 1
        else: tn += 1
    observed = {"labels": tp + fp + tn + fn, "false_positives": fp, "false_negatives": fn,
                "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1),
                "false_positive_rate": fp / max(fp + tn, 1)}
    return render(request, "mfs/model_monitor.html", {"models": models, "observed": observed})


@require_roles(ROLE_ADMIN)
def api_keys(request):
    secret = None
    if request.method == "POST":
        name = (request.POST.get("name") or "ingestion").strip()[:100]
        _, secret = IngestionAPIKey.issue(request.user.organization, name)
        audit("api_key.created", organization=request.user.organization, actor=request.user, metadata={"name": name})
    keys = IngestionAPIKey.objects.filter(organization=request.user.organization)
    return render(request, "mfs/api_keys.html", {"keys": keys, "secret": secret})


@require_roles(ROLE_ADMIN)
def api_key_revoke(request, pk):
    key = get_object_or_404(IngestionAPIKey, pk=pk, organization=request.user.organization)
    if request.method == "POST":
        key.is_active = False
        key.save(update_fields=["is_active", "updated_at"])
        audit("api_key.revoked", organization=request.user.organization, actor=request.user, target=key,
              metadata={"name": key.name, "prefix": key.prefix})
        messages.success(request, "Ingestion key revoked.")
    return redirect("mfs:api_keys")


@require_roles(ROLE_ADMIN, ROLE_ANALYST, ROLE_REVIEWER)
def assistant(request):
    form = AssistantForm(request.POST or None); result = None; error = None
    if request.method == "POST" and form.is_valid():
        try: result = answer_question(request.user.organization, request.user, form.cleaned_data["question"])
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exception:
            error = f"Local LLM is unavailable or returned an invalid tool request ({exception.__class__.__name__})."
    return render(request, "mfs/assistant.html", {"form": form, "result": result, "error": error})
