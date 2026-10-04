from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from . import db, statistics_engine
from .models import InsightsReport
from .seed import seed_demo_orders


@login_required
def report_list(request):
    reports = InsightsReport.objects.filter(organization=request.user.organization)
    return render(
        request,
        "insights/report_list.html",
        {"reports": reports, "default_window_days": settings.INSIGHTS_WINDOW_DAYS},
    )


@login_required
def report_detail(request, pk):
    report = get_object_or_404(InsightsReport, pk=pk, organization=request.user.organization)
    return render(request, "insights/report_detail.html", {"report": report})


@login_required
def run_report(request):
    if request.method != "POST":
        return redirect("insights:list")

    try:
        window_days = int(request.POST.get("window_days", settings.INSIGHTS_WINDOW_DAYS))
    except ValueError:
        window_days = settings.INSIGHTS_WINDOW_DAYS
    window_days = max(1, min(window_days, 365))

    try:
        conn = db.get_connection()
        rows = db.fetch_orders(conn, window_days)
        conn.close()
    except Exception as error:
        report = InsightsReport.objects.create(
            organization=request.user.organization,
            requested_by=request.user,
            window_days=window_days,
            status=InsightsReport.STATUS_ERROR,
            error_message=str(error),
        )
        messages.error(request, "Could not connect to the database. See the report for details.")
        return redirect("insights:detail", pk=report.pk)

    summary = statistics_engine.compute_summary(rows)
    trend = statistics_engine.compute_trend(rows)
    anomalies = statistics_engine.detect_anomalies(rows)
    insight_text = statistics_engine.generate_insights(summary, trend, anomalies)

    report = InsightsReport.objects.create(
        organization=request.user.organization,
        requested_by=request.user,
        window_days=window_days,
        status=InsightsReport.STATUS_OK if summary["total_orders"] else InsightsReport.STATUS_NO_DATA,
        summary=summary,
        trend=trend,
        anomalies=anomalies,
        insight_text=insight_text,
    )
    return redirect("insights:detail", pk=report.pk)


@login_required
def seed_demo(request):
    if request.method == "POST":
        count = seed_demo_orders()
        messages.success(request, f"Loaded {count} demo orders into the database.")
    return redirect("insights:list")
