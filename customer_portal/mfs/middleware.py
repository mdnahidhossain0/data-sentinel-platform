import uuid


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Correlation-ID", "")
        try:
            request.correlation_id = str(uuid.UUID(incoming)) if incoming else str(uuid.uuid4())
        except ValueError:
            request.correlation_id = str(uuid.uuid4())
        response = self.get_response(request)
        response["X-Correlation-ID"] = request.correlation_id
        return response
