# Ethos API Contracts

## Governance Agent
`POST /governance/auditor/{audit_id}`

Response:
```json
{
  "audit_id": "uuid",
  "state": "report",
  "recommendation": "Apply Equalized Odds post-processing...",
  "rationale": "REPORT prompt output...",
  "actions": ["run_equalized_odds", "track_accuracy_and_group_rates"],
  "recalled_memories": [
    {
      "audit_id": "uuid",
      "stage": "mitigation",
      "score": 0.7123,
      "memory_text": "stage=mitigation | dataset=q3.csv ...",
      "metadata": {"method": "equalized_odds", "accuracy_delta": -0.021}
    }
  ]
}
```

## Deep Inspection
`POST /inspection/deep/{audit_id}`

Response:
```json
{
  "audit_id": "uuid",
  "protected_attribute": "ethnicity",
  "engine": "dowhy",
  "dag_edges": [{"source": "ethnicity", "target": "hired"}],
  "proxy_findings": [
    {
      "feature": "zip_code",
      "proxy_strength": 0.42,
      "treatment_effect": 0.09,
      "risk_score": 0.0378,
      "is_proxy": true,
      "explanation": "zip_code has proxy-strength ..."
    }
  ],
  "tcav_concepts": [
    {
      "concept": "Leadership",
      "tcav_score": 0.66,
      "sensitivity": 0.68,
      "prevalence": 0.31,
      "direction": "increases hire propensity",
      "summary": "Leadership concept ..."
    }
  ]
}
```

## DP Report + Certificate
`GET /report/{audit_id}?epsilon=1.0`
- Returns PDF stream.
- Header `X-Audit-Certificate` returns SHA-256 hash.

`GET /certificate/{audit_id}`
```json
{
  "audit_id": "uuid",
  "hash_algorithm": "sha256",
  "report_hash": "hex",
  "epsilon": 1.0,
  "payload": {"dp_metrics": {"disparate_impact": 0.81}},
  "created_at": "2026-04-15T..."
}
```
