from datetime import datetime, timedelta

from django.test import SimpleTestCase

from . import statistics_engine as stats


def row(days_ago, amount, status, base=None):
    base = base or datetime(2026, 9, 1, 12, 0, 0)
    created_at = (base - timedelta(days=days_ago)).isoformat()
    return (created_at, amount, status)


class SummaryTests(SimpleTestCase):
    def test_empty_rows_returns_zeroed_summary(self):
        summary = stats.compute_summary([])
        self.assertEqual(summary["total_orders"], 0)
        self.assertIsNone(summary["success_rate"])

    def test_known_values_produce_exact_statistics(self):
        rows = [
            row(0, 100.0, "success"),
            row(0, 200.0, "success"),
            row(0, 300.0, "success"),
            row(0, 50.0, "failed"),
        ]
        summary = stats.compute_summary(rows)
        self.assertEqual(summary["total_orders"], 4)
        self.assertEqual(summary["success_count"], 3)
        self.assertEqual(summary["failed_count"], 1)
        self.assertEqual(summary["success_rate"], 75.0)
        self.assertEqual(summary["total_revenue"], 600.0)
        self.assertEqual(summary["average_order_value"], 200.0)
        self.assertEqual(summary["median_order_value"], 200.0)

    def test_failed_orders_excluded_from_revenue_and_averages(self):
        rows = [row(0, 1000.0, "failed"), row(0, 10.0, "success")]
        summary = stats.compute_summary(rows)
        self.assertEqual(summary["total_revenue"], 10.0)
        self.assertEqual(summary["average_order_value"], 10.0)


class PercentChangeTests(SimpleTestCase):
    def test_zero_baseline_both_zero_is_zero_percent(self):
        self.assertEqual(stats._percent_change(0, 0), 0.0)

    def test_zero_baseline_nonzero_new_is_100_percent(self):
        self.assertEqual(stats._percent_change(0, 5), 100.0)

    def test_standard_increase(self):
        self.assertEqual(stats._percent_change(100, 150), 50.0)

    def test_standard_decrease(self):
        self.assertEqual(stats._percent_change(200, 150), -25.0)


class TrendTests(SimpleTestCase):
    def test_insufficient_days_returns_none(self):
        self.assertIsNone(stats.compute_trend([row(0, 10, "success")]))

    def test_recent_dip_is_detected(self):
        base = datetime(2026, 9, 30, 12, 0, 0)
        rows = []
        for d in range(10, 3, -1):
            rows.append(row(d, 100.0, "success", base=base))
        for d in range(3, -1, -1):
            rows.append(row(d, 20.0, "success", base=base))

        trend = stats.compute_trend(rows, window_days=4)
        self.assertLess(trend["revenue_change_pct"], 0)


class AnomalyTests(SimpleTestCase):
    def test_flat_series_has_no_anomalies(self):
        base = datetime(2026, 9, 30, 12, 0, 0)
        rows = [row(d, 100.0, "success", base=base) for d in range(10)]
        self.assertEqual(stats.detect_anomalies(rows), [])

    def test_single_spike_is_flagged(self):
        base = datetime(2026, 9, 30, 12, 0, 0)
        rows = [row(d, 100.0, "success", base=base) for d in range(1, 10)]
        rows.append(row(0, 5000.0, "success", base=base))
        anomalies = stats.detect_anomalies(rows)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["direction"], "above")

    def test_short_series_skips_detection(self):
        rows = [row(0, 10.0, "success"), row(1, 5000.0, "success")]
        self.assertEqual(stats.detect_anomalies(rows), [])


class InsightTextTests(SimpleTestCase):
    def test_no_orders_gives_single_message(self):
        summary = stats.compute_summary([])
        self.assertEqual(stats.generate_insights(summary, None, []), ["No order data is available for this period."])

    def test_insights_are_plain_strings_no_llm_markup(self):
        rows = [row(0, 100.0, "success"), row(1, 50.0, "failed")]
        summary = stats.compute_summary(rows)
        trend = stats.compute_trend(rows)
        anomalies = stats.detect_anomalies(rows)
        insights = stats.generate_insights(summary, trend, anomalies)
        self.assertTrue(insights)
        for line in insights:
            self.assertIsInstance(line, str)
