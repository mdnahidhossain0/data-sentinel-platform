from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Installation


@login_required
def installation_list(request):
    installations = Installation.objects.select_related("customer", "license")

    q = request.GET.get("q", "").strip()
    if q:
        installations = installations.filter(customer__company_name__icontains=q)

    paginator = Paginator(installations, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "installations/installation_list.html", {"page": page, "q": q})


@login_required
def installation_detail(request, pk):
    installation = get_object_or_404(Installation.objects.select_related("customer", "license"), pk=pk)
    return render(request, "installations/installation_detail.html", {"installation": installation})
