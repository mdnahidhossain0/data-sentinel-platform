from customers.models import Customer


def authenticate_partner(request):
    external_id = request.headers.get("X-Sentinel-Account", "")
    secret = request.headers.get("X-Sentinel-Secret", "")

    if not external_id or not secret:
        return None

    try:
        customer = Customer.objects.get(external_id=external_id)
    except (Customer.DoesNotExist, ValueError):
        return None

    if not customer.check_api_secret(secret):
        return None

    return customer
