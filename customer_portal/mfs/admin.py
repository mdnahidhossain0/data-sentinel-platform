from django.contrib import admin

from . import models


for model in (
    models.MfsCustomer, models.Wallet, models.Account, models.Merchant, models.Agent,
    models.Device, models.Location, models.Beneficiary, models.MfsSession,
    models.Transaction, models.TransactionEvent, models.ModelVersion,
    models.RiskAssessment, models.RiskFactor, models.ModelPrediction,
    models.FraudAlert, models.ReviewCase, models.ReviewDecision, models.TransactionLabel, models.DataSource,
    models.SchemaVersion, models.SchemaTable, models.SchemaColumn,
    models.DataPipeline, models.DataQualityMetric, models.BusinessKPISnapshot, models.MfsAuditEvent,
    models.IngestionAPIKey,
):
    admin.site.register(model)
