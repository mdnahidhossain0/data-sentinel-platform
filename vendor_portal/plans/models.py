from django.db import models


class Plan(models.Model):
    INTERVAL_MONTH = "month"
    INTERVAL_YEAR = "year"
    INTERVAL_CHOICES = [(INTERVAL_MONTH, "Monthly"), (INTERVAL_YEAR, "Yearly")]

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    billing_interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES)
    price_usd = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    duration_days = models.PositiveIntegerField()
    max_installations = models.PositiveIntegerField(default=1)
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_usd"]

    def __str__(self):
        return f"{self.name} (${self.price_usd}/{self.billing_interval})"
