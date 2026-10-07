import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models


class TenantModel(models.Model):
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class MfsCustomer(TenantModel):
    external_id = models.CharField(max_length=100)
    display_name = models.CharField(max_length=255, blank=True, default="")
    phone_masked = models.CharField(max_length=32, blank=True, default="")
    risk_tier = models.CharField(max_length=20, default="STANDARD")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_mfs_customer")]


class Wallet(TenantModel):
    external_id = models.CharField(max_length=100)
    customer = models.ForeignKey(MfsCustomer, on_delete=models.PROTECT, related_name="wallets")
    status = models.CharField(max_length=20, default="ACTIVE")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_wallet")]


class Account(TenantModel):
    external_id = models.CharField(max_length=100)
    customer = models.ForeignKey(MfsCustomer, on_delete=models.PROTECT, related_name="accounts")
    account_type = models.CharField(max_length=32, default="MFS")
    status = models.CharField(max_length=20, default="ACTIVE")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_mfs_account")]


class Merchant(TenantModel):
    external_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, default="")
    historical_risk = models.FloatField(default=0.0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_merchant")]


class Agent(TenantModel):
    external_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    historical_risk = models.FloatField(default=0.0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_agent")]


class Device(TenantModel):
    external_id = models.CharField(max_length=100)
    customer = models.ForeignKey(MfsCustomer, null=True, blank=True, on_delete=models.SET_NULL, related_name="devices")
    fingerprint_hash = models.CharField(max_length=64, blank=True, default="")
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_device")]


class Location(TenantModel):
    external_id = models.CharField(max_length=100)
    country_code = models.CharField(max_length=2, blank=True, default="")
    region = models.CharField(max_length=100, blank=True, default="")
    latitude_rounded = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    longitude_rounded = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_location")]


class Beneficiary(TenantModel):
    external_id = models.CharField(max_length=100)
    customer = models.ForeignKey(MfsCustomer, on_delete=models.PROTECT, related_name="beneficiaries")
    first_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_beneficiary")]


class MfsSession(TenantModel):
    external_id = models.CharField(max_length=100)
    customer = models.ForeignKey(MfsCustomer, on_delete=models.PROTECT, related_name="sessions")
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.SET_NULL)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_mfs_session")]


class Transaction(TenantModel):
    STATUS_PENDING = "PENDING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [(STATUS_PENDING, "Pending"), (STATUS_SUCCESS, "Success"), (STATUS_FAILED, "Failed")]

    external_id = models.CharField(max_length=100)
    customer = models.ForeignKey(MfsCustomer, on_delete=models.PROTECT, related_name="transactions")
    wallet = models.ForeignKey(Wallet, null=True, blank=True, on_delete=models.PROTECT)
    account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT)
    merchant = models.ForeignKey(Merchant, null=True, blank=True, on_delete=models.PROTECT)
    agent = models.ForeignKey(Agent, null=True, blank=True, on_delete=models.PROTECT)
    beneficiary = models.ForeignKey(Beneficiary, null=True, blank=True, on_delete=models.PROTECT)
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.PROTECT)
    session = models.ForeignKey(MfsSession, null=True, blank=True, on_delete=models.PROTECT)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="BDT")
    transaction_type = models.CharField(max_length=32, default="TRANSFER")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    occurred_at = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=100, default="api")
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    device_changed = models.BooleanField(default=False)
    location_changed = models.BooleanField(default=False)
    transactions_last_10_min = models.PositiveIntegerField(default=0)
    new_beneficiaries = models.PositiveIntegerField(default=0)
    historical_average_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["-occurred_at"]
        constraints = [models.UniqueConstraint(fields=["organization", "external_id"], name="uniq_transaction")]
        indexes = [models.Index(fields=["organization", "occurred_at"]), models.Index(fields=["organization", "status"])]


class TransactionEvent(TenantModel):
    STATUS_RECEIVED = "RECEIVED"
    STATUS_PUBLISHED = "PUBLISHED"
    STATUS_PROCESSED = "PROCESSED"
    STATUS_FAILED = "FAILED"
    event_id = models.UUIDField(default=uuid.uuid4)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=64, default="transaction.created")
    schema_version = models.CharField(max_length=16, default="1.0")
    correlation_id = models.UUIDField(db_index=True)
    occurred_at = models.DateTimeField()
    status = models.CharField(max_length=20, default=STATUS_RECEIVED)
    retry_count = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "event_id"], name="uniq_transaction_event")]


class ModelVersion(TenantModel):
    STATUS_TRAINING = "TRAINING"
    STATUS_CANDIDATE = "CANDIDATE"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_RETIRED = "RETIRED"
    name = models.CharField(max_length=100, default="hybrid-risk")
    version = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default=STATUS_CANDIDATE)
    artifact_path = models.CharField(max_length=500, blank=True, default="")
    dataset_version = models.CharField(max_length=64)
    feature_version = models.CharField(max_length=64, default="v1")
    parameters = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict)
    trained_at = models.DateTimeField(null=True, blank=True)
    is_synthetic = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "name", "version"], name="uniq_model_version")]


class RiskAssessment(TenantModel):
    LEVEL_LOW = "LOW"
    LEVEL_MEDIUM = "MEDIUM"
    LEVEL_HIGH = "HIGH"
    DECISION_ALLOW = "ALLOW"
    DECISION_MONITOR = "MONITOR"
    DECISION_REVIEW = "REVIEW"
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="risk_assessments")
    model_version = models.ForeignKey(ModelVersion, null=True, blank=True, on_delete=models.SET_NULL)
    score = models.PositiveSmallIntegerField()
    level = models.CharField(max_length=10)
    decision = models.CharField(max_length=16)
    fraud_probability = models.FloatField()
    anomaly_score = models.FloatField(default=0.0)
    rule_score = models.FloatField(default=0.0)
    inference_duration_ms = models.PositiveIntegerField(default=0)
    explanation = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]


class RiskFactor(models.Model):
    assessment = models.ForeignKey(RiskAssessment, on_delete=models.CASCADE, related_name="factors")
    code = models.CharField(max_length=64)
    label = models.CharField(max_length=255)
    contribution = models.FloatField()
    source = models.CharField(max_length=20, default="RULE")
    evidence = models.JSONField(default=dict)


class ModelPrediction(TenantModel):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="predictions")
    model_version = models.ForeignKey(ModelVersion, null=True, blank=True, on_delete=models.SET_NULL)
    probability = models.FloatField()
    predicted_label = models.BooleanField()
    feature_values = models.JSONField(default=dict)
    feature_contributions = models.JSONField(default=dict)


class FraudAlert(TenantModel):
    STATUS_NEW = "NEW"
    STATUS_UNDER_REVIEW = "UNDER_REVIEW"
    STATUS_CONFIRMED_RISK = "CONFIRMED_RISK"
    STATUS_FALSE_POSITIVE = "FALSE_POSITIVE"
    STATUS_RESOLVED = "RESOLVED"
    STATUS_ESCALATED = "ESCALATED"
    STATUS_CHOICES = [(value, value.replace("_", " ").title()) for value in (
        STATUS_NEW, STATUS_UNDER_REVIEW, STATUS_CONFIRMED_RISK, STATUS_FALSE_POSITIVE, STATUS_RESOLVED, STATUS_ESCALATED
    )]
    assessment = models.OneToOneField(RiskAssessment, on_delete=models.CASCADE, related_name="alert")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_NEW)
    title = models.CharField(max_length=255)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ReviewCase(TenantModel):
    alert = models.OneToOneField(FraudAlert, on_delete=models.CASCADE, related_name="review_case")
    status = models.CharField(max_length=24, default="OPEN")
    priority = models.CharField(max_length=16, default="HIGH")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]


class ReviewDecision(TenantModel):
    DECISION_APPROVE = "APPROVE"
    DECISION_REJECT = "REJECT"
    DECISION_ESCALATE = "ESCALATE"
    DECISION_CHOICES = [(DECISION_APPROVE, "Approve"), (DECISION_REJECT, "Reject"), (DECISION_ESCALATE, "Escalate")]
    review_case = models.ForeignKey(ReviewCase, on_delete=models.CASCADE, related_name="decisions")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    decision = models.CharField(max_length=16, choices=DECISION_CHOICES)
    reason = models.CharField(max_length=255)
    comments = models.TextField(blank=True, default="")
    risk_score = models.PositiveSmallIntegerField()
    model_version = models.CharField(max_length=64, blank=True, default="")
    evidence = models.JSONField(default=dict)


class TransactionLabel(TenantModel):
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name="ground_truth")
    is_fraud = models.BooleanField()
    source = models.CharField(max_length=32, default="HUMAN_REVIEW")
    labeled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.CharField(max_length=500, blank=True, default="")


class DataSource(TenantModel):
    ENGINE_POSTGRESQL = "postgresql"
    ENGINE_SQLITE = "sqlite3"
    name = models.CharField(max_length=100)
    engine = models.CharField(max_length=20, choices=[(ENGINE_POSTGRESQL, "PostgreSQL"), (ENGINE_SQLITE, "SQLite")])
    host = models.CharField(max_length=255, blank=True, default="")
    port = models.PositiveIntegerField(null=True, blank=True)
    database_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, blank=True, default="")
    encrypted_password = models.TextField(blank=True, default="")
    ssl_required = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default="PENDING")
    last_discovered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="uniq_data_source")]


class SchemaVersion(models.Model):
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="schema_versions")
    version = models.PositiveIntegerField()
    fingerprint = models.CharField(max_length=64)
    changes = models.JSONField(default=dict)
    discovered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["data_source", "version"], name="uniq_schema_version")]
        ordering = ["-version"]


class SchemaTable(models.Model):
    schema_version = models.ForeignKey(SchemaVersion, on_delete=models.CASCADE, related_name="tables")
    schema_name = models.CharField(max_length=255, default="public")
    table_name = models.CharField(max_length=255)
    row_estimate = models.BigIntegerField(null=True, blank=True)
    primary_key = models.JSONField(default=list)
    foreign_keys = models.JSONField(default=list)
    indexes = models.JSONField(default=list)


class SchemaColumn(models.Model):
    table = models.ForeignKey(SchemaTable, on_delete=models.CASCADE, related_name="columns")
    name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=255)
    nullable = models.BooleanField(default=True)
    ordinal_position = models.PositiveIntegerField()
    is_pii = models.BooleanField(default=False)


class DataPipeline(TenantModel):
    name = models.CharField(max_length=100)
    pipeline_type = models.CharField(max_length=32)
    status = models.CharField(max_length=20, default="IDLE")
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    records_processed = models.PositiveBigIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="uniq_data_pipeline")]


class DataQualityMetric(TenantModel):
    pipeline = models.ForeignKey(DataPipeline, null=True, blank=True, on_delete=models.SET_NULL)
    metric_name = models.CharField(max_length=100)
    value = models.FloatField()
    threshold = models.FloatField(null=True, blank=True)
    passed = models.BooleanField(default=True)
    measured_at = models.DateTimeField(auto_now_add=True)
    dimensions = models.JSONField(default=dict)


class BusinessKPISnapshot(TenantModel):
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    metrics = models.JSONField(default=dict)
    is_synthetic = models.BooleanField(default=False)
    generated_by = models.CharField(max_length=32, default="SYSTEM")

    class Meta:
        ordering = ["-period_end"]


class MfsAuditEvent(models.Model):
    organization = models.ForeignKey("accounts.Organization", null=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100, db_index=True)
    target_type = models.CharField(max_length=100, blank=True, default="")
    target_id = models.CharField(max_length=100, blank=True, default="")
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class IngestionAPIKey(TenantModel):
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=12, db_index=True)
    secret_hash = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, organization, name):
        if not organization.external_id:
            raise ValueError("Organization must be provisioned with an external_id before issuing an ingestion key")
        raw = f"dsk_{secrets.token_urlsafe(32)}"
        obj = cls.objects.create(
            organization=organization,
            name=name,
            prefix=raw[:12],
            secret_hash=hashlib.sha256(raw.encode()).hexdigest(),
        )
        return obj, raw

    def matches(self, raw):
        return secrets.compare_digest(self.secret_hash, hashlib.sha256(raw.encode()).hexdigest())
