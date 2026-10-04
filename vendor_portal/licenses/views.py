import csv
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import license_manager_required
from audit.services import log_action

from . import services
from .forms import ChangePlanForm, ExtendLicenseForm, GenerateLicenseForm, RevokeLicenseForm
from .models import License


@login_required
def license_list(request):
    licenses = License.objects.select_related("customer", "plan")

    q = request.GET.get("q", "").strip()
    if q:
        licenses = licenses.filter(customer__company_name__icontains=q)

    status = request.GET.get("status", "").strip()
    if status:
        licenses = licenses.filter(status=status)

    paginator = Paginator(licenses, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "licenses/license_list.html",
        {"page": page, "q": q, "status": status, "status_choices": License.STATUS_CHOICES},
    )


@login_required
def license_detail(request, pk):
    license_obj = get_object_or_404(License.objects.select_related("customer", "plan"), pk=pk)
    return render(request, "licenses/license_detail.html", {"license": license_obj})


@login_required
@license_manager_required
def license_generate(request):
    if request.method == "POST":
        form = GenerateLicenseForm(request.POST)
        if form.is_valid():
            start_date = datetime.combine(form.cleaned_data["start_date"], datetime.min.time())
            start_date = timezone.make_aware(start_date) if timezone.is_naive(start_date) else start_date
            license_obj = services.generate_license(
                customer=form.cleaned_data["customer"],
                plan=form.cleaned_data["plan"],
                start_date=start_date,
                duration_days=form.cleaned_data.get("duration_days") or None,
                created_by=request.user,
                notes=form.cleaned_data.get("notes", ""),
            )
            log_action(request, "license_generated", target=license_obj, metadata={"plan": license_obj.plan.code})
            messages.success(request, "License generated.")
            return redirect("licenses:detail", pk=license_obj.pk)
    else:
        form = GenerateLicenseForm()
    return render(request, "licenses/license_generate.html", {"form": form})


@login_required
@license_manager_required
def license_revoke(request, pk):
    license_obj = get_object_or_404(License, pk=pk)
    if request.method == "POST":
        form = RevokeLicenseForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data["reason"]
            details = form.cleaned_data.get("details", "")
            services.revoke_license(license_obj, reason=reason)
            log_action(request, "license_revoked", target=license_obj, metadata={"reason": reason, "details": details})
            messages.success(request, "License revoked.")
            return redirect("licenses:detail", pk=license_obj.pk)
    else:
        form = RevokeLicenseForm()
    return render(request, "licenses/license_revoke.html", {"form": form, "license": license_obj})


@login_required
@license_manager_required
def license_suspend(request, pk):
    license_obj = get_object_or_404(License, pk=pk)
    if request.method == "POST":
        services.suspend_license(license_obj)
        log_action(request, "license_suspended", target=license_obj)
        messages.success(request, "License suspended.")
    return redirect("licenses:detail", pk=license_obj.pk)


@login_required
@license_manager_required
def license_reactivate(request, pk):
    license_obj = get_object_or_404(License, pk=pk)
    if request.method == "POST":
        services.reactivate_license(license_obj)
        log_action(request, "license_reactivated", target=license_obj)
        messages.success(request, "License reactivated.")
    return redirect("licenses:detail", pk=license_obj.pk)


@login_required
@license_manager_required
def license_extend(request, pk):
    license_obj = get_object_or_404(License, pk=pk)
    if request.method == "POST":
        form = ExtendLicenseForm(request.POST)
        if form.is_valid():
            days = form.cleaned_data["additional_days"]
            services.extend_license(license_obj, additional_days=days)
            log_action(request, "license_extended", target=license_obj, metadata={"additional_days": days})
            messages.success(request, f"License extended by {days} days.")
            return redirect("licenses:detail", pk=license_obj.pk)
    else:
        form = ExtendLicenseForm()
    return render(request, "licenses/license_extend.html", {"form": form, "license": license_obj})


@login_required
@license_manager_required
def license_change_plan(request, pk):
    license_obj = get_object_or_404(License, pk=pk)
    if request.method == "POST":
        form = ChangePlanForm(request.POST)
        if form.is_valid():
            new_plan = form.cleaned_data["plan"]
            services.change_plan(license_obj, new_plan=new_plan)
            log_action(request, "license_plan_changed", target=license_obj, metadata={"new_plan": new_plan.code})
            messages.success(request, "Plan changed.")
            return redirect("licenses:detail", pk=license_obj.pk)
    else:
        form = ChangePlanForm()
    return render(request, "licenses/license_change_plan.html", {"form": form, "license": license_obj})


@login_required
@license_manager_required
def license_regenerate(request, pk):
    license_obj = get_object_or_404(License, pk=pk)
    if request.method == "POST":
        new_license = services.regenerate_license(license_obj, actor=request.user)
        log_action(request, "license_regenerated", target=new_license, metadata={"previous_license": license_obj.pk})
        messages.success(request, "License regenerated.")
        return redirect("licenses:detail", pk=new_license.pk)
    return redirect("licenses:detail", pk=license_obj.pk)


@login_required
def license_download(request, pk):
    license_obj = get_object_or_404(License, pk=pk)
    content = (
        f"Customer: {license_obj.customer.company_name}\n"
        f"Plan: {license_obj.plan.name}\n"
        f"Status: {license_obj.effective_status}\n"
        f"Start: {license_obj.start_date.isoformat()}\n"
        f"Expires: {license_obj.expires_at.isoformat()}\n\n"
        f"{license_obj.license_key}\n"
    )
    response = HttpResponse(content, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="license-{license_obj.pk}.txt"'
    return response


@login_required
def license_export(request):
    licenses = License.objects.select_related("customer", "plan")

    q = request.GET.get("q", "").strip()
    if q:
        licenses = licenses.filter(customer__company_name__icontains=q)

    status = request.GET.get("status", "").strip()
    if status:
        licenses = licenses.filter(status=status)

    response = HttpResponse(content_type="text/csv")
    filename = f"licenses-{datetime.utcnow():%Y%m%d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["ID", "Customer", "Plan", "Status", "Start Date", "Expires At", "Last Check-in"])
    for license_obj in licenses:
        writer.writerow([
            license_obj.pk,
            license_obj.customer.company_name,
            license_obj.plan.name,
            license_obj.effective_status,
            license_obj.start_date.isoformat(),
            license_obj.expires_at.isoformat(),
            license_obj.last_check_in.isoformat() if license_obj.last_check_in else "",
        ])
    return response
