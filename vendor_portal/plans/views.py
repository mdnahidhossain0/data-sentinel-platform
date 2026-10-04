from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import license_manager_required
from audit.services import log_action

from .forms import PlanForm
from .models import Plan


@login_required
def plan_list(request):
    plans = Plan.objects.all()
    return render(request, "plans/plan_list.html", {"plans": plans})


@login_required
@license_manager_required
def plan_create(request):
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            plan = form.save()
            log_action(request, "plan_created", target=plan)
            messages.success(request, f"Created plan {plan.name}.")
            return redirect("plans:list")
    else:
        form = PlanForm()
    return render(request, "plans/plan_form.html", {"form": form, "title": "New Plan"})


@login_required
@license_manager_required
def plan_edit(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    if request.method == "POST":
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            log_action(request, "plan_updated", target=plan)
            messages.success(request, "Plan updated.")
            return redirect("plans:list")
    else:
        form = PlanForm(instance=plan)
    return render(request, "plans/plan_form.html", {"form": form, "title": plan.name})


@login_required
@license_manager_required
def plan_toggle_active(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    if request.method == "POST":
        plan.is_active = not plan.is_active
        plan.save(update_fields=["is_active", "updated_at"])
        log_action(request, "plan_toggled", target=plan, metadata={"is_active": plan.is_active})
    return redirect("plans:list")
