from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SupportTicketForm
from .models import SupportTicket


@login_required
def ticket_list(request):
    tickets = SupportTicket.objects.filter(organization=request.user.organization)
    return render(request, "support/ticket_list.html", {"tickets": tickets})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk, organization=request.user.organization)
    return render(request, "support/ticket_detail.html", {"ticket": ticket})


@login_required
def ticket_create(request):
    if request.method == "POST":
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.organization = request.user.organization
            ticket.created_by = request.user
            ticket.save()
            messages.success(request, "Support ticket created.")
            return redirect("support:detail", pk=ticket.pk)
    else:
        form = SupportTicketForm()
    return render(request, "support/ticket_form.html", {"form": form})
