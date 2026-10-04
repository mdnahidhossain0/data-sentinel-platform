from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .models import AuditEvent


@login_required
def audit_log_list(request):
    events = AuditEvent.objects.select_related("actor").all()

    action = request.GET.get("action", "").strip()
    if action:
        events = events.filter(action__icontains=action)

    q = request.GET.get("q", "").strip()
    if q:
        events = events.filter(target_type__icontains=q) | events.filter(target_id__icontains=q)

    paginator = Paginator(events, 50)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "audit/audit_log_list.html", {"page": page, "action": action, "q": q})
