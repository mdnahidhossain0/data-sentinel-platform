import json

import requests
from django.conf import settings
from django.db.models import Avg, Count
from django.utils import timezone

from .audit import audit
from .models import Merchant, RiskAssessment, Transaction


TOOLS = {
    "recent_high_risk_transactions": "Recent high-risk transactions in a bounded time window",
    "top_high_risk_merchants": "Merchants ranked by high-risk transaction count",
    "explain_transaction": "Risk factors for one transaction identifier",
    "compare_suspicious_volume": "Compare today's suspicious volume with yesterday",
}


def _choose_tool(question):
    prompt = (
        "Choose exactly one approved read-only tool for the user question. Return JSON only with keys tool and arguments. "
        f"Approved tools: {json.dumps(TOOLS)}. Never produce SQL. Question: {question}"
    )
    response = requests.post(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate", json={
        "model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json",
    }, timeout=settings.OLLAMA_TIMEOUT_SECONDS)
    response.raise_for_status()
    decision = json.loads(response.json()["response"])
    if decision.get("tool") not in TOOLS:
        raise ValueError("The model selected an unapproved tool")
    return decision["tool"], decision.get("arguments") or {}


def _execute(organization, tool, arguments):
    if tool == "recent_high_risk_transactions":
        minutes = min(max(int(arguments.get("minutes", 30)), 1), 1440)
        rows = RiskAssessment.objects.filter(organization=organization, level="HIGH",
            transaction__occurred_at__gte=timezone.now() - timezone.timedelta(minutes=minutes)).select_related("transaction")[:20]
        return [{"transaction_id": row.transaction.external_id, "score": row.score, "reason": row.explanation} for row in rows]
    if tool == "top_high_risk_merchants":
        minutes = min(max(int(arguments.get("minutes", 60)), 1), 10080)
        return list(Merchant.objects.filter(organization=organization,
            transaction__risk_assessments__level="HIGH", transaction__occurred_at__gte=timezone.now() - timezone.timedelta(minutes=minutes))
            .annotate(alerts=Count("transaction"), average_score=Avg("transaction__risk_assessments__score"))
            .order_by("-alerts").values("external_id", "name", "alerts", "average_score")[:10])
    if tool == "explain_transaction":
        tx_id = str(arguments.get("transaction_id", ""))
        assessment = RiskAssessment.objects.filter(organization=organization, transaction__external_id=tx_id).prefetch_related("factors").first()
        if not assessment: return {"error": "Transaction or assessment not found"}
        return {"transaction_id": tx_id, "score": assessment.score, "level": assessment.level,
                "factors": [{"label": f.label, "contribution": f.contribution, "source": f.source} for f in assessment.factors.all()]}
    if tool == "compare_suspicious_volume":
        today = timezone.localdate()
        counts = []
        for day in (today - timezone.timedelta(days=1), today):
            counts.append(RiskAssessment.objects.filter(organization=organization, level="HIGH", created_at__date=day).count())
        return {"yesterday": counts[0], "today": counts[1], "change": counts[1] - counts[0]}
    raise ValueError("Unapproved tool")


def answer_question(organization, user, question):
    tool, arguments = _choose_tool(question[:1000])
    result = _execute(organization, tool, arguments)
    prompt = ("Explain this approved analytics result concisely. Do not add facts not present in the JSON. "
              f"Question: {question}\nResult: {json.dumps(result, default=str)}")
    response = requests.post(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate", json={
        "model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False,
    }, timeout=settings.OLLAMA_TIMEOUT_SECONDS)
    response.raise_for_status()
    answer = response.json()["response"].strip()
    audit("assistant.query", organization=organization, actor=user, metadata={"tool": tool, "arguments": arguments})
    return {"answer": answer, "tool": tool, "data": result}
