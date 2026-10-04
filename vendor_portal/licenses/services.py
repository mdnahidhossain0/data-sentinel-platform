from datetime import timedelta

from django.utils import timezone

from .crypto import sign_license_payload
from .models import License


def _build_payload(customer, plan, start_date, expires_at):
    return {
        "customer": customer.company_name,
        "plan": plan.code,
        "issued_at": timezone.now().isoformat(),
        "start_date": start_date.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


def generate_license(customer, plan, start_date, duration_days=None, created_by=None, notes=""):
    duration = duration_days or plan.duration_days
    expires_at = start_date + timedelta(days=duration)

    payload = _build_payload(customer, plan, start_date, expires_at)
    license_key = sign_license_payload(payload)

    status = License.STATUS_ACTIVE if start_date <= timezone.now() else License.STATUS_PENDING

    return License.objects.create(
        customer=customer,
        plan=plan,
        license_key=license_key,
        start_date=start_date,
        expires_at=expires_at,
        status=status,
        created_by=created_by,
        notes=notes,
    )


def revoke_license(license_obj, reason, actor=None):
    license_obj.status = License.STATUS_REVOKED
    license_obj.revocation_reason = reason
    license_obj.save(update_fields=["status", "revocation_reason", "updated_at"])
    return license_obj


def suspend_license(license_obj):
    license_obj.status = License.STATUS_SUSPENDED
    license_obj.save(update_fields=["status", "updated_at"])
    return license_obj


def reactivate_license(license_obj):
    license_obj.status = License.STATUS_ACTIVE if not license_obj.is_expired else License.STATUS_EXPIRED
    license_obj.save(update_fields=["status", "updated_at"])
    return license_obj


def extend_license(license_obj, additional_days, actor=None):
    new_expiry = license_obj.expires_at + timedelta(days=additional_days)
    payload = _build_payload(license_obj.customer, license_obj.plan, license_obj.start_date, new_expiry)
    new_key = sign_license_payload(payload)

    license_obj.license_key = new_key
    license_obj.expires_at = new_expiry
    if license_obj.status == License.STATUS_EXPIRED:
        license_obj.status = License.STATUS_ACTIVE
    license_obj.save(update_fields=["license_key", "expires_at", "status", "updated_at"])
    return license_obj


def change_plan(license_obj, new_plan, actor=None):
    payload = _build_payload(license_obj.customer, new_plan, license_obj.start_date, license_obj.expires_at)
    new_key = sign_license_payload(payload)

    license_obj.plan = new_plan
    license_obj.license_key = new_key
    license_obj.save(update_fields=["plan", "license_key", "updated_at"])
    return license_obj


def regenerate_license(license_obj, actor=None):
    new_license = generate_license(
        customer=license_obj.customer,
        plan=license_obj.plan,
        start_date=timezone.now(),
        duration_days=max((license_obj.expires_at - timezone.now()).days, 1),
        created_by=actor,
        notes=f"Regenerated from license #{license_obj.pk}",
    )
    license_obj.status = License.STATUS_REVOKED
    license_obj.revocation_reason = "Regenerated"
    license_obj.superseded_by = new_license
    license_obj.save(update_fields=["status", "revocation_reason", "superseded_by", "updated_at"])
    return new_license
