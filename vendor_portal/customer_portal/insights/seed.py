import random
import sqlite3
from datetime import datetime, timedelta

from django.conf import settings

from .db import SCHEMA


def seed_demo_orders(days=120, seed=42):
    random.seed(seed)
    conn = sqlite3.connect(settings.INSIGHTS_DB_PATH)
    with conn:
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.execute(SCHEMA)

        now = datetime.utcnow()
        rows = []
        order_id = 1

        for day_offset in range(days, 0, -1):
            day = now - timedelta(days=day_offset)
            base_orders = random.randint(18, 32)

            is_dip = 0 <= day_offset <= 4
            if is_dip:
                base_orders = max(2, base_orders // 4)

            for _ in range(base_orders):
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                timestamp = day.replace(hour=hour, minute=minute, second=random.randint(0, 59))
                amount = round(random.uniform(15, 220), 2)
                failure_rate = 0.35 if is_dip else 0.06
                status = "failed" if random.random() < failure_rate else "success"
                rows.append((order_id, timestamp.isoformat(), amount, status))
                order_id += 1

        conn.executemany("INSERT INTO orders (id, created_at, amount, status) VALUES (?, ?, ?, ?)", rows)

    conn.close()
    return len(rows)
