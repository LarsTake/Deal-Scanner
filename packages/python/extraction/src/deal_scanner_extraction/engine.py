from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from deal_scanner_core.models import ProductDetection
from deal_scanner_scoring import RiskSignal


@dataclass(frozen=True)
class ProductRule:
    product_type: str
    manufacturer: str | None
    model: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class RiskRule:
    signal_type: str
    weight: int
    pattern: re.Pattern[str]
    positive: bool = False


class RuleAnalysis:
    def __init__(
        self,
        products: list[ProductDetection],
        risk_signals: list[RiskSignal],
        contradictions: list[str] | None = None,
    ) -> None:
        self.products = products
        self.risk_signals = risk_signals
        self.contradictions = contradictions or []


class RuleExtractor:
    product_rules = (
        ProductRule(
            "gpu",
            "NVIDIA",
            "RTX 4070 Super",
            re.compile(r"\b(?:geforce\s*)?(?:rtx\s*)?4070\s*(?:super|s)\b", re.I),
        ),
        ProductRule(
            "quick_release",
            "Fanatec",
            "QR2",
            re.compile(r"\bqr\s*2\b", re.I),
        ),
        ProductRule(
            "quick_release",
            "Fanatec",
            "QR1",
            re.compile(r"\bqr\s*1\b", re.I),
        ),
        ProductRule(
            "digital_video_system",
            "DJI",
            "O3 Air Unit",
            re.compile(r"\b(?:dji\s*)?o\s*3(?:\s*air\s*unit)?\b", re.I),
        ),
        ProductRule(
            "digital_video_system",
            "DJI",
            "Vista",
            re.compile(r"\b(?:caddx\s*)?(?:dji\s*)?vista\b", re.I),
        ),
        ProductRule(
            "receiver_protocol",
            None,
            "ELRS",
            re.compile(r"\b(?:express\s*lrs|elrs)\b", re.I),
        ),
    )
    risk_rules = (
        RiskRule(
            "paypal_friends_only",
            35,
            re.compile(r"paypal\s*(?:freunde|friends)|nur\s*pp\s*f&f", re.I),
        ),
        RiskRule(
            "external_payment_link",
            35,
            re.compile(r"(?:zahlungs|payment)[- ]?link|bit\.ly/|tinyurl\.com/", re.I),
        ),
        RiskRule(
            "off_platform_communication",
            15,
            re.compile(r"(?:nur|bitte)\s*(?:per\s*)?(?:whatsapp|telegram)", re.I),
        ),
        RiskRule(
            "unusual_time_pressure",
            15,
            re.compile(r"(?:nur\s*heute|sofort\s*entscheiden|muss\s*heute\s*weg)", re.I),
        ),
        RiskRule(
            "no_function_test",
            10,
            re.compile(r"(?:kein|nicht)\s*(?:funktions|funktion)[- ]?test", re.I),
        ),
        RiskRule(
            "pickup_possible",
            10,
            re.compile(r"abholung\s*(?:ist\s*)?(?:m[oö]glich|bevorzugt)", re.I),
            positive=True,
        ),
        RiskRule(
            "function_test_possible",
            10,
            re.compile(r"(?:funktionstest|testen)\s*(?:ist\s*)?(?:vor\s*ort\s*)?m[oö]glich", re.I),
            positive=True,
        ),
        RiskRule(
            "buyer_protection",
            15,
            re.compile(r"(?:k[aä]uferschutz|sicher\s*bezahlen)", re.I),
            positive=True,
        ),
    )

    @staticmethod
    def normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value)
        return re.sub(r"\s+", " ", normalized).strip()

    def analyze(self, title: str, description: str) -> RuleAnalysis:
        sources = (
            ("title", self.normalize_text(title)),
            ("description", self.normalize_text(description)),
        )
        products: list[ProductDetection] = []
        seen_products: set[tuple[str, str]] = set()
        for source_name, source_text in sources:
            for product_rule in self.product_rules:
                match = product_rule.pattern.search(source_text)
                product_key = (product_rule.product_type, product_rule.model)
                if match and product_key not in seen_products:
                    products.append(
                        ProductDetection(
                            product_type=product_rule.product_type,
                            manufacturer=product_rule.manufacturer,
                            model=product_rule.model,
                            confidence=0.99 if source_name == "title" else 0.95,
                            sources=[source_name],
                            evidence=match.group(0),
                        )
                    )
                    seen_products.add(product_key)

        combined = f"{sources[0][1]}\n{sources[1][1]}"
        risk_signals: list[RiskSignal] = []
        for risk_rule in self.risk_rules:
            match = risk_rule.pattern.search(combined)
            if match:
                risk_signals.append(
                    RiskSignal(
                        type=risk_rule.signal_type,
                        weight=risk_rule.weight,
                        confidence=0.95,
                        evidence=match.group(0),
                        positive=risk_rule.positive,
                        source="titleOrDescription",
                    )
                )

        contradictions: list[str] = []
        if re.search(r"\b4070\s*ti\b", title, re.I) and re.search(r"\b4070\s*super\b", description, re.I):
            contradictions.append("Titel nennt RTX 4070 Ti, Beschreibung nennt RTX 4070 Super.")
        return RuleAnalysis(products, risk_signals, contradictions)
