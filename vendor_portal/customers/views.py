from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import license_manager_required
from audit.models import AuditEvent
from audit.services import log_action
from installations.models import Installation
from licenses import services as license_services
from licenses.models import License

from . import provisioning
from .forms import CustomerCreateForm, CustomerForm
from .models import Customer


@login_required
def customer_list(request):
    customers = Customer.objects.all()

    q = request.GET.get("q", "").strip()
    if q:
        customers = customers.filter(company_name__icontains=q) | customers.filter(email__icontains=q)

    status = request.GET.get("status", "").strip()
    if status:
        customers = customers.filter(status=status)

    paginator = Paginator(customers.order_by("company_name"), 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "customers/customer_list.html",
        {"page": page, "q": q, "status": status, "status_choices": Customer.STATUS_CHOICES},
    )


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    licenses = License.objects.filter(customer=customer).order_by("-created_at")
    installations = Installation.objects.filter(customer=customer).order_by("-last_check_in")
    activity = AuditEvent.objects.filter(target_type="Customer", target_id=str(customer.pk))[:20]
    return render(
        request,
        "customers/customer_detail.html",
        {"customer": customer, "licenses": licenses, "installations": installations, "activity": activity},
    )


@login_required
@license_manager_required
def customer_create(request):
    if request.method == "POST":
        form = CustomerCreateForm(request.POST)
        if form.is_valid():
            customer = Customer.objects.create(
                company_name=form.cleaned_data["company_name"],
                contact_person=form.cleaned_data["contact_person"],
                email=form.cleaned_data["email"],
                phone=form.cleaned_data["phone"],
                country=form.cleaned_data["country"],
                organization_type=form.cleaned_data["organization_type"],
                notes=form.cleaned_data["notes"],
            )
            raw_secret = customer.set_api_secret()
            customer.save(update_fields=["api_secret_hash", "updated_at"])
            log_action(request, "customer_created", target=customer)

            start_date = datetime.combine(form.cleaned_data["start_date"], datetime.min.time())
            start_date = timezone.make_aware(start_date) if timezone.is_naive(start_date) else start_date
            license_obj = license_services.generate_license(
                customer=customer,
                plan=form.cleaned_data["plan"],
                start_date=start_date,
                duration_days=form.cleaned_data.get("duration_days") or None,
                created_by=request.user,
            )
            log_action(request, "license_generated", target=license_obj, metadata={"plan": license_obj.plan.code})

            provisioning_error = None
            try:
                provisioning.provision_customer_account(
                    customer=customer,
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["initial_password"],
                    raw_api_secret=raw_secret,
                )
            except provisioning.ProvisioningError as error:
                provisioning_error = str(error)
                log_action(request, "customer_portal_provision_failed", target=customer, metadata={"error": provisioning_error})
            else:
                log_action(request, "customer_portal_provisioned", target=customer)

            return render(
                request,
                "customers/customer_created.html",
                {
                    "customer": customer,
                    "license": license_obj,
                    "temp_password": form.cleaned_data["initial_password"],
                    "provisioning_error": provisioning_error,
                },
            )
    else:
        form = CustomerCreateForm()
    return render(request, "customers/customer_create.html", {"form": form})


@login_required
@license_manager_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            log_action(request, "customer_updated", target=customer)
            messages.success(request, "Customer updated.")
            return redirect("customers:detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)
    return render(request, "customers/customer_form.html", {"form": form, "title": customer.company_name})


def _push_status(request, customer):
    try:
        provisioning.push_status_update(customer)
    except provisioning.ProvisioningError as error:
        log_action(request, "customer_portal_status_push_failed", target=customer, metadata={"error": str(error)})
        messages.warning(
            request,
            f"Status updated here, but the Customer Portal could not be reached ({error}). "
            "Use \u201cRetry Portal Sync\u201d below.",
        )
    else:
        log_action(request, "customer_portal_status_synced", target=customer, metadata={"status": customer.status})


@login_required
@license_manager_required
def customer_suspend(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        customer.status = Customer.STATUS_SUSPENDED
        customer.save(update_fields=["status", "updated_at"])
        log_action(request, "customer_suspended", target=customer)
        _push_status(request, customer)
        messages.success(request, f"{customer.company_name} suspended.")
    return redirect("customers:detail", pk=customer.pk)


@login_required
@license_manager_required
def customer_reactivate(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        customer.status = Customer.STATUS_ACTIVE
        customer.save(update_fields=["status", "updated_at"])
        log_action(request, "customer_reactivated", target=customer)
        _push_status(request, customer)
        messages.success(request, f"{customer.company_name} reactivated.")
    return redirect("customers:detail", pk=customer.pk)


@login_required
@license_manager_required
def customer_archive(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        customer.status = Customer.STATUS_ARCHIVED
        customer.save(update_fields=["status", "updated_at"])
        log_action(request, "customer_archived", target=customer)
        _push_status(request, customer)
        messages.success(request, f"{customer.company_name} archived.")
    return redirect("customers:list")


@login_required
@license_manager_required
def customer_retry_portal_sync(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        _push_status(request, customer)
    return redirect("customers:detail", pk=customer.pk)


@login_required
@license_manager_required
def customer_regenerate_api_secret(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    raw_secret = None
    sync_error = None
    if request.method == "POST":
        raw_secret = customer.set_api_secret()
        customer.save(update_fields=["api_secret_hash", "updated_at"])
        log_action(request, "customer_api_secret_regenerated", target=customer)
        try:
            provisioning.push_secret_rotation(customer, raw_api_secret=raw_secret)
        except provisioning.ProvisioningError as error:
            sync_error = str(error)
            log_action(request, "customer_portal_provision_failed", target=customer, metadata={"error": sync_error})
    return render(
        request,
        "customers/api_secret.html",
        {"customer": customer, "raw_secret": raw_secret, "sync_error": sync_error},
    )


@login_required
@license_manager_required
def customer_reset_portal_password(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    new_password = None
    error = None
    if request.method == "POST":
        from .forms import _generate_temp_password

        new_password = _generate_temp_password()
        raw_secret = customer.set_api_secret()
        customer.save(update_fields=["api_secret_hash", "updated_at"])
        try:
            provisioning.provision_customer_account(
                customer=customer, email=customer.email, password=new_password, raw_api_secret=raw_secret
            )
        except provisioning.ProvisioningError as exc:
            error = str(exc)
            log_action(request, "customer_portal_provision_failed", target=customer, metadata={"error": error})
        else:
            log_action(request, "customer_portal_password_reset", target=customer)
    return render(
        request,
        "customers/reset_password.html",
        {"customer": customer, "new_password": new_password, "error": error},
    )
