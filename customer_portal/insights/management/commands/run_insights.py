from django.core.management.base import BaseCommand

from accounts.models import Organization
from insights import db, statistics_engine
from insights.models import InsightsReport


class Command(BaseCommand):
    help = "Runs a statistics pass against the configured database for every organization (cron-friendly)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None)

    def handle(self, *args, **options):
        from django.conf import settings

        window_days = options["days"] or settings.INSIGHTS_WINDOW_DAYS

        try:
            conn = db.get_connection()
            rows = db.fetch_orders(conn, window_days)
            conn.close()
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Database connection failed: {error}"))
            return

        summary = statistics_engine.compute_summary(rows)
        trend = statistics_engine.compute_trend(rows)
        anomalies = statistics_engine.detect_anomalies(rows)
        insight_text = statistics_engine.generate_insights(summary, trend, anomalies)

        for organization in Organization.objects.all():
            InsightsReport.objects.create(
                organization=organization,
                window_days=window_days,
                status=InsightsReport.STATUS_OK if summary["total_orders"] else InsightsReport.STATUS_NO_DATA,
                summary=summary,
                trend=trend,
                anomalies=anomalies,
                insight_text=insight_text,
            )

        self.stdout.write(self.style.SUCCESS(f"Generated insights for {Organization.objects.count()} organization(s)."))
