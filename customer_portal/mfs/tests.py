import json
import sqlite3
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import CustomerUser, Organization
from mfs.assistant import answer_question
from mfs.connectors import discover_schema, encrypt_password
from mfs.ml import train_model
from mfs.kpis import calculate_business_kpis, create_business_kpi_snapshot
from mfs.models import DataSource, FraudAlert, IngestionAPIKey, ReviewCase, ReviewDecision, RiskAssessment, TransactionEvent
from mfs.risk import assess_transaction
from mfs.services import ValidationError, ingest_transaction
from mfs import streaming


def payload(index=1, risky=False):
    return {
        "event_id": str(uuid.uuid4()), "transaction_id": f"TX-{index}", "customer_id": "CUS-1",
        "amount": 90000 if risky else 500, "historical_average_amount": 1000,
        "occurred_at": timezone.now().isoformat(), "status": "SUCCESS", "device_changed": risky,
        "location_changed": risky, "transactions_last_10_min": 18 if risky else 1,
        "new_beneficiaries": 5 if risky else 0,
    }


class TenantAndIngestionTests(TestCase):
    def setUp(self):
        self.a = Organization.objects.create(name="A", external_id=uuid.uuid4())
        self.b = Organization.objects.create(name="B", external_id=uuid.uuid4())

    def test_event_id_is_idempotent_per_tenant(self):
        body = payload()
        first_tx, first_event, created = ingest_transaction(self.a, body)
        second_tx, second_event, created_again = ingest_transaction(self.a, body)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first_tx.pk, second_tx.pk)
        self.assertEqual(first_event.pk, second_event.pk)

    def test_duplicate_transaction_with_new_event_is_rejected(self):
        body = payload()
        ingest_transaction(self.a, body)
        body["event_id"] = str(uuid.uuid4())
        with self.assertRaises(ValidationError): ingest_transaction(self.a, body)

    def test_api_key_is_hashed_and_scoped(self):
        key, raw = IngestionAPIKey.issue(self.a, "test")
        self.assertNotIn(raw, key.secret_hash)
        self.assertTrue(key.matches(raw))
        self.assertEqual(key.organization, self.a)

    def test_cross_tenant_transaction_is_404(self):
        tx, _, _ = ingest_transaction(self.b, payload())
        user = CustomerUser.objects.create_user(username="a@example.com", password="strong-password-1", organization=self.a,
                                                role=CustomerUser.ROLE_VIEWER)
        self.client.force_login(user)
        self.assertEqual(self.client.get(f"/mfs/transactions/{tx.pk}/").status_code, 404)

    @patch("mfs.api_views.publish", return_value={"topic": "mfs.transactions", "partition": 0, "offset": 1})
    def test_authenticated_ingestion_publishes_minimal_event(self, publish_mock):
        _, raw = IngestionAPIKey.issue(self.a, "test")
        response = self.client.post("/api/v1/mfs/transactions/ingest/", json.dumps(payload()),
                                    content_type="application/json", headers={"Authorization": f"Bearer {raw}"})
        self.assertEqual(response.status_code, 202)
        event = publish_mock.call_args.args[1]
        self.assertNotIn("amount", event)
        self.assertNotIn("customer_id", event)
        self.assertEqual(event["tenant_id"], str(self.a.external_id))


class StreamingConfigurationTests(TestCase):
    @patch("mfs.streaming.KafkaProducer")
    def test_producer_uses_supported_ordered_delivery_settings(self, producer_class):
        previous = streaming._producer
        streaming._producer = None
        try:
            self.assertIs(streaming.producer(), producer_class.return_value)
            options = producer_class.call_args.kwargs
            self.assertEqual(options["acks"], "all")
            self.assertEqual(options["retries"], 5)
            self.assertEqual(options["max_in_flight_requests_per_connection"], 1)
            self.assertNotIn("enable_idempotence", options)
        finally:
            streaming._producer = previous


class RiskEngineTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Risk Org")

    def test_real_training_metrics_and_high_risk_review_flow(self):
        with tempfile.TemporaryDirectory() as directory, self.settings(MODEL_ARTIFACT_DIR=directory):
            model = train_model(self.org, rows=1200, seed=9)
            for metric in ("precision", "recall", "f1", "roc_auc", "false_positive_rate"):
                self.assertIn(metric, model.metrics)
            self.assertTrue(Path(model.artifact_path).exists())
            tx, _, _ = ingest_transaction(self.org, payload(risky=True))
            assessment = assess_transaction(tx)
            self.assertGreaterEqual(assessment.score, 0)
            self.assertLessEqual(assessment.score, 100)
            self.assertTrue(assessment.factors.exists())
            if assessment.level == "HIGH":
                self.assertTrue(FraudAlert.objects.filter(assessment=assessment).exists())
                self.assertTrue(ReviewCase.objects.filter(alert__assessment=assessment).exists())


class ConnectorTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Connector Org")

    def test_sqlite_schema_is_discovered_and_versioned(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as handle:
            connection = sqlite3.connect(handle.name)
            connection.execute("CREATE TABLE wallets (id INTEGER PRIMARY KEY, phone TEXT, balance NUMERIC)")
            connection.commit(); connection.close()
            source = DataSource.objects.create(organization=self.org, name="demo", engine="sqlite3", database_name=handle.name, ssl_required=False)
            version, changed = discover_schema(source)
            self.assertTrue(changed)
            self.assertEqual(version.tables.get(table_name="wallets").columns.get(name="phone").is_pii, True)
            same_version, changed_again = discover_schema(source)
            self.assertFalse(changed_again)
            self.assertEqual(version.pk, same_version.pk)

    def test_connector_secret_is_encrypted(self):
        key = Fernet.generate_key().decode()
        with self.settings(DATA_SOURCE_ENCRYPTION_KEY=key):
            encrypted = encrypt_password("database-secret")
        self.assertNotIn("database-secret", encrypted)


class AssistantSecurityTests(TestCase):
    def test_unapproved_llm_tool_is_rejected(self):
        org = Organization.objects.create(name="AI Org")
        user = CustomerUser.objects.create_user(username="ai@example.com", password="strong-password-1", organization=org,
                                                role=CustomerUser.ROLE_RISK_ANALYST)
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"response": '{"tool":"run_raw_sql","arguments":{"sql":"DROP TABLE x"}}'}
        with patch("mfs.assistant.requests.post", return_value=response):
            with self.assertRaises(ValueError): answer_question(org, user, "delete all data")


class BusinessKPITests(TestCase):
    def test_measured_kpis_use_persisted_workflow_data(self):
        org = Organization.objects.create(name="KPI Org", external_id=uuid.uuid4())
        reviewer = CustomerUser.objects.create_user(
            username="reviewer@example.com", password="strong-password-1", organization=org,
            role=CustomerUser.ROLE_REVIEWER,
        )
        tx, _, _ = ingest_transaction(org, payload(risky=True))
        assessment = RiskAssessment.objects.create(
            organization=org, transaction=tx, score=91, level="HIGH", decision="REVIEW",
            fraud_probability=.9, anomaly_score=.8, rule_score=.9,
        )
        alert = FraudAlert.objects.create(organization=org, assessment=assessment, title="High risk test")
        case = ReviewCase.objects.create(organization=org, alert=alert)
        ReviewDecision.objects.create(
            organization=org, review_case=case, reviewer=reviewer, decision=ReviewDecision.DECISION_REJECT,
            reason="Confirmed test risk", risk_score=91,
        )
        alert.status = FraudAlert.STATUS_CONFIRMED_RISK
        alert.save()
        metrics = calculate_business_kpis(org)
        self.assertEqual(metrics["transactions_scored_pct"], 100.0)
        self.assertEqual(metrics["high_risk_detected"], 1)
        self.assertEqual(metrics["high_risk_reviewed"], 1)
        self.assertEqual(metrics["confirmed_risk_transaction_value"], 90000.0)
        snapshot = create_business_kpi_snapshot(org)
        self.assertEqual(snapshot.metrics["review_completion_pct"], 100.0)
