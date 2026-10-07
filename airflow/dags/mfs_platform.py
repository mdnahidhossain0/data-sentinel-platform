from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


DEFAULTS = {"owner": "data-sentinel", "retries": 2, "retry_delay": timedelta(minutes=2)}
PROJECT = "cd /opt/data-sentinel/customer_portal && python manage.py mfs_pipeline"


def pipeline(dag_id, action, schedule, description):
    with DAG(
        dag_id=dag_id, description=description, default_args=DEFAULTS,
        start_date=datetime(2025, 1, 1), schedule=schedule, catchup=False,
        tags=["data-sentinel", "mfs"], max_active_runs=1,
    ) as dag:
        BashOperator(task_id=action, bash_command=f"{PROJECT} {action}", execution_timeout=timedelta(hours=2))
    return dag


mfs_ingestion_validation = pipeline("mfs_ingestion_validation", "validate_ingestion", "*/10 * * * *", "Validate real-time ingestion outcomes")
mfs_data_quality = pipeline("mfs_data_quality", "data_quality", "0 * * * *", "Measure transaction completeness and validity")
mfs_historical_backfill = pipeline("mfs_historical_backfill", "historical_backfill", None, "Controlled historical source backfill")
mfs_feature_dataset = pipeline("mfs_feature_dataset", "prepare_features", "15 1 * * *", "Prepare versioned feature data")
mfs_model_training = pipeline("mfs_model_training", "train_model", "0 2 * * 0", "Train candidate transaction risk models")
mfs_model_evaluation = pipeline("mfs_model_evaluation", "evaluate_model", "0 3 * * 0", "Evaluate the active model with recorded metrics")
mfs_schema_change_detection = pipeline("mfs_schema_change_detection", "discover_schemas", "30 * * * *", "Discover and diff connected database schemas")
mfs_analytics_aggregation = pipeline("mfs_analytics_aggregation", "aggregate_analytics", "*/15 * * * *", "Aggregate operational risk KPIs")
mfs_risk_report = pipeline("mfs_risk_report", "risk_report", "0 6 * * *", "Generate tenant-scoped risk reports")
mfs_failed_pipeline_recovery = pipeline("mfs_failed_pipeline_recovery", "recover_failed", "*/5 * * * *", "Reset failed events for controlled retry")
