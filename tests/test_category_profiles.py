from pathlib import Path

from deal_scanner_extraction import load_category_profiles


def test_all_versioned_category_profiles_are_build_validated() -> None:
    profiles = load_category_profiles(Path("schemas"))
    assert set(profiles) == {"computer", "simracing", "fpv", "general"}
    for profile in profiles.values():
        assert profile.product_types
        assert profile.extraction_rules
        assert profile.market_rules
        assert profile.completeness_fields
        assert profile.scoring_weights
        assert profile.risk_weights
