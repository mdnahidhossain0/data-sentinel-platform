# Business KPI definitions and evidence

The Business KPIs page reports tenant-scoped outcomes calculated from persisted operational records for a selectable 1–365 day period. It is available to organization administrators, compliance users, auditors, and analysts at `/mfs/business-kpis/`.

## Definitions

| KPI | Calculation | Why it matters |
|---|---|---|
| Scoring coverage | assessed transactions / ingested transactions | Shows how completely the detection pipeline covers incoming activity. |
| Average detection latency | mean `RiskAssessment.created_at - Transaction.created_at` | Measures how quickly a transaction receives a risk result. |
| High-risk review completion | reviewed high-risk cases / detected high-risk transactions | Shows whether the human-review workflow is keeping up. |
| Average review time | mean `ReviewDecision.created_at - ReviewCase.opened_at` | Measures analyst turnaround time. |
| False-positive rate | reviewed false positives / reviewed transactions | Quantifies customer/analyst friction among transactions with ground truth. |
| Analyst override rate | decisions differing from the model decision / reviewed transactions | Indicates how often human judgment changes the automated outcome. |
| Confirmed-risk transactions | reviewed transactions with a positive ground-truth label | Counts risks confirmed by human/external evidence. |
| Confirmed-risk transaction value | sum of transaction amounts for confirmed-risk labels | Describes value associated with confirmed risk; it is **not** claimed as prevented loss or savings. |

Counts and rates are based only on records available in the selected period. A false-positive rate is meaningful only where a human or external label exists. The page labels generated/demo-source periods as synthetic so prototype results cannot be mistaken for production business impact.

## Reproducible evidence

Generate and persist a current snapshot:

```bash
docker compose exec -T customer-web python manage.py generate_business_kpis --days 30
```

The daily `mfs_risk_report` Airflow DAG performs the same snapshot operation. Historical snapshots shown on the page provide an auditable record of the exact metrics and period. Source fields remain in normalized MFS tables, allowing each aggregate to be independently reconciled.

Business value beyond confirmed transaction value—such as prevented loss, recovered revenue, investigation cost, customer churn, or regulatory penalties avoided—requires approved finance/outcome data and is deliberately not inferred by this system.
