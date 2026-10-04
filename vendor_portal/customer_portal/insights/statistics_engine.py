import statistics
from collections import defaultdict
from datetime import datetime


def _parse_rows(rows):
    parsed = []
    for created_at, amount, status in rows:
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        parsed.append({"created_at": created_at, "amount": float(amount), "status": status})
    return parsed


def compute_summary(rows):
    orders = _parse_rows(rows)
    if not orders:
        return {
            "total_orders": 0, "total_revenue": 0.0, "success_count": 0, "failed_count": 0,
            "success_rate": None, "average_order_value": None, "median_order_value": None,
            "revenue_stdev": None,
        }

    successful = [o for o in orders if o["status"] == "success"]
    failed = [o for o in orders if o["status"] == "failed"]
    amounts = [o["amount"] for o in successful] or [0.0]

    return {
        "total_orders": len(orders),
        "total_revenue": round(sum(amounts), 2),
        "success_count": len(successful),
        "failed_count": len(failed),
        "success_rate": round(len(successful) / len(orders) * 100, 1),
        "average_order_value": round(statistics.mean(amounts), 2),
        "median_order_value": round(statistics.median(amounts), 2),
        "revenue_stdev": round(statistics.pstdev(amounts), 2) if len(amounts) > 1 else 0.0,
    }


def _daily_totals(rows):
    orders = _parse_rows(rows)
    totals = defaultdict(float)
    counts = defaultdict(int)
    successes = defaultdict(int)
    for order in orders:
        day = order["created_at"].date().isoformat()
        counts[day] += 1
        if order["status"] == "success":
            totals[day] += order["amount"]
            successes[day] += 1
    days = sorted(counts.keys())
    return days, totals, counts, successes


def _percent_change(old, new):
    if old == 0:
        return 0.0 if new == 0 else 100.0
    return round((new - old) / old * 100, 1)


def compute_trend(rows, window_days=7):
    days, totals, counts, successes = _daily_totals(rows)
    if len(days) < 2:
        return None

    split = max(len(days) - window_days, len(days) // 2)
    recent_days, earlier_days = days[split:], days[:split]
    if not recent_days or not earlier_days:
        return None

    recent_revenue = sum(totals[d] for d in recent_days)
    earlier_revenue = sum(totals[d] for d in earlier_days)
    recent_orders = sum(counts[d] for d in recent_days)
    earlier_orders = sum(counts[d] for d in earlier_days)
    recent_success_rate = (sum(successes[d] for d in recent_days) / recent_orders * 100) if recent_orders else None
    earlier_success_rate = (sum(successes[d] for d in earlier_days) / earlier_orders * 100) if earlier_orders else None

    return {
        "recent_days": len(recent_days),
        "earlier_days": len(earlier_days),
        "revenue_change_pct": _percent_change(earlier_revenue, recent_revenue),
        "order_count_change_pct": _percent_change(earlier_orders, recent_orders),
        "recent_success_rate": round(recent_success_rate, 1) if recent_success_rate is not None else None,
        "earlier_success_rate": round(earlier_success_rate, 1) if earlier_success_rate is not None else None,
    }


def detect_anomalies(rows, z_threshold=2.0):
    days, totals, counts, successes = _daily_totals(rows)
    if len(days) < 4:
        return []

    daily_values = [totals[d] for d in days]
    mean = statistics.mean(daily_values)
    stdev = statistics.pstdev(daily_values)
    if stdev == 0:
        return []

    anomalies = []
    for day, value in zip(days, daily_values):
        z_score = (value - mean) / stdev
        if abs(z_score) >= z_threshold:
            anomalies.append({
                "date": day,
                "revenue": round(value, 2),
                "z_score": round(z_score, 2),
                "direction": "above" if z_score > 0 else "below",
            })
    return anomalies


def generate_insights(summary, trend, anomalies):
    insights = []

    if summary["total_orders"] == 0:
        return ["No order data is available for this period."]

    if trend:
        change = trend["revenue_change_pct"]
        if change > 5:
            insights.append(f"Revenue is up {change}% in the most recent {trend['recent_days']} day(s) compared to the prior period.")
        elif change < -5:
            insights.append(f"Revenue is down {abs(change)}% in the most recent {trend['recent_days']} day(s) compared to the prior period.")
        else:
            insights.append(f"Revenue is roughly flat ({change:+.1f}%) compared to the prior period.")

        if trend["recent_success_rate"] is not None and trend["earlier_success_rate"] is not None:
            rate_change = round(trend["recent_success_rate"] - trend["earlier_success_rate"], 1)
            if rate_change <= -3:
                insights.append(
                    f"Payment success rate dropped {abs(rate_change)} points, from {trend['earlier_success_rate']}% "
                    f"to {trend['recent_success_rate']}% — worth investigating."
                )
            elif rate_change >= 3:
                insights.append(f"Payment success rate improved {rate_change} points, now at {trend['recent_success_rate']}%.")

    if summary["success_rate"] is not None and summary["success_rate"] < 90:
        insights.append(f"Overall payment success rate for this period is {summary['success_rate']}%, below the typical 90%+ range.")

    if anomalies:
        below = [a for a in anomalies if a["direction"] == "below"]
        above = [a for a in anomalies if a["direction"] == "above"]
        if below:
            dates = ", ".join(a["date"] for a in below[:5])
            insights.append(f"{len(below)} day(s) had unusually low revenue (2+ standard deviations below average): {dates}.")
        if above:
            dates = ", ".join(a["date"] for a in above[:5])
            insights.append(f"{len(above)} day(s) had unusually high revenue (2+ standard deviations above average): {dates}.")
    else:
        insights.append("No statistically unusual days detected in this period.")

    return insights
