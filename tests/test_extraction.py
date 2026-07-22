from deal_scanner_extraction import RuleExtractor
from deal_scanner_scoring import RiskScoreEngine


def models(text: str) -> set[str]:
    analysis = RuleExtractor().analyze(text, "")
    return {product.model for product in analysis.products}


def test_rtx_aliases_normalize_to_exact_model() -> None:
    assert models("Gaming PC mit RTX4070S 12GB") == {"RTX 4070 Super"}
    assert models("Geforce RTX 4070 Super") == {"RTX 4070 Super"}
    assert models("4070s guter Zustand") == {"RTX 4070 Super"}


def test_qr1_and_qr2_remain_distinct() -> None:
    assert models("Fanatec Wheel mit QR1") == {"QR1"}
    assert models("Fanatec Wheel mit QR2") == {"QR2"}


def test_o3_vista_and_elrs_remain_distinct() -> None:
    assert models("5 Zoll Copter DJI O3 mit ELRS") == {"O3 Air Unit", "ELRS"}
    assert models("Caddx Vista und ExpressLRS") == {"Vista", "ELRS"}


def test_paypal_friends_creates_signal_but_missing_seller_does_not() -> None:
    analysis = RuleExtractor().analyze("RTX 4070", "Nur Paypal Freunde. Keine Verkäuferinfos.")
    types = {signal.type for signal in analysis.risk_signals}
    assert "paypal_friends_only" in types
    assert "missing_seller" not in types
    assert RiskScoreEngine().score(analysis.risk_signals).score > 0


def test_positive_signals_are_marked_positive() -> None:
    analysis = RuleExtractor().analyze("PC", "Abholung möglich, Funktionstest vor Ort möglich.")
    assert all(signal.positive for signal in analysis.risk_signals)
