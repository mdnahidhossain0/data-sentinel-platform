from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, redirect, render

from audit.services import log_action

from .permissions import super_admin_required

StaffUser = get_user_model()


class StaffUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = StaffUser
        fields = ("username", "email", "role")


@login_required
@super_admin_required
def admin_user_list(request):
    users = StaffUser.objects.all().order_by("username")
    return render(request, "accounts/admin_user_list.html", {"users": users})


@login_required
@super_admin_required
def admin_user_create(request):
    if request.method == "POST":
        form = StaffUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            log_action(request, "admin_user_created", target=user, metadata={"role": user.role})
            messages.success(request, f"Created admin user {user.username}.")
            return redirect("accounts:admin_user_list")
    else:
        form = StaffUserCreationForm()
    return render(request, "accounts/admin_user_form.html", {"form": form})


@login_required
@super_admin_required
def admin_user_toggle_active(request, pk):
    user = get_object_or_404(StaffUser, pk=pk)
    if request.method == "POST":
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        log_action(request, "admin_user_toggled", target=user, metadata={"is_active": user.is_active})
        messages.success(request, f"{user.username} is now {'active' if user.is_active else 'disabled'}.")
    return redirect("accounts:admin_user_list")
