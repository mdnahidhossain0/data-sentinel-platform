import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from customers.models import Customer
from installations.models import Installation
from licenses.models import License


@login_required
def home(request):
    now = timezone.now()
    week_from_now = now + timedelta(days=7)

    licenses = License.objects.select_related("plan")

    active_licenses = licenses.filter(status=License.STATUS_ACTIVE, expires_at__gt=now)
    expired_licenses = licenses.filter(expires_at__lte=now, status=License.STATUS_ACTIVE) | licenses.filter(
        status=License.STATUS_EXPIRED
    )
    revoked_licenses = licenses.filter(status=License.STATUS_REVOKED)
    suspended_licenses = licenses.filter(status=License.STATUS_SUSPENDED)
    expiring_soon = active_licenses.filter(expires_at__lte=week_from_now)

    monthly_revenue = sum(
        (license_obj.plan.price_usd for license_obj in active_licenses if license_obj.plan.billing_interval == "month"),
        Decimal("0"),
    )
    yearly_revenue = sum(
        (license_obj.plan.price_usd for license_obj in active_licenses if license_obj.plan.billing_interval == "year"),
        Decimal("0"),
    )
    mrr = monthly_revenue + (yearly_revenue / Decimal("12"))

    installations = list(Installation.objects.select_related("license"))
    active_installations = [installation for installation in installations if installation.status == Installation.STATUS_ONLINE]
    offline_installations = [installation for installation in installations if installation.status == Installation.STATUS_OFFLINE]

    thirty_days_ago = now - timedelta(days=30)
    daily_activations = {}
    for license_obj in licenses.filter(created_at__gte=thirty_days_ago):
        day_key = license_obj.created_at.date().isoformat()
        daily_activations[day_key] = daily_activations.get(day_key, 0) + 1

    activation_series = [{"date": (thirty_days_ago + timedelta(days=i)).date().isoformat(), "count": 0} for i in range(31)]
    for point in activation_series:
        point["count"] = daily_activations.get(point["date"], 0)

    status_breakdown = {
        "Active": active_licenses.count(),
        "Expired": expired_licenses.count(),
        "Revoked": revoked_licenses.count(),
        "Suspended": suspended_licenses.count(),
        "Pending": licenses.filter(status=License.STATUS_PENDING).count(),
    }

    context = {
        "total_customers": Customer.objects.count(),
        "active_license_count": active_licenses.count(),
        "expired_license_count": expired_licenses.count(),
        "revoked_license_count": revoked_licenses.count(),
        "expiring_soon_count": expiring_soon.count(),
        "mrr": mrr.quantize(Decimal("0.01")),
        "yearly_revenue": yearly_revenue.quantize(Decimal("0.01")),
        "active_installation_count": len(active_installations),
        "offline_installation_count": len(offline_installations),
        "recent_activations": licenses.order_by("-created_at")[:5],
        "recent_revocations": revoked_licenses.order_by("-updated_at")[:5],
        "recent_checkins": Installation.objects.exclude(last_check_in__isnull=True).order_by("-last_check_in")[:5],
        "status_breakdown_json": json.dumps(status_breakdown),
        "activation_series_json": json.dumps(activation_series),
    }
    return render(request, "dashboard/home.html", context)
