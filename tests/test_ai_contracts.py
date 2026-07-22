import pytest
from deal_scanner_core.models import TextAnalysisResult
from pydantic import ValidationError


def test_ai_risk_signal_requires_evidence_and_bounded_confidence() -> None:
    with pytest.raises(ValidationError):
        TextAnalysisResult.model_validate(
            {
                "category": "computer",
                "products": [],
                "attributes": [],
                "riskSignals": [{"signalType": "external_payment", "severity": "high", "confidence": 2}],
                "contradictions": [],
                "missingInformation": [],
                "overallConfidence": 0.8,
                "schemaVersion": "1.0.0",
            }
        )
