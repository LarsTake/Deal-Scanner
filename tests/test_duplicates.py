from deal_scanner_extraction import listing_text_fingerprint, listing_text_similarity, normalize_listing_text


def test_listing_text_fingerprint_normalizes_case_spacing_and_urls() -> None:
    first = listing_text_fingerprint("Gaming-PC", "Wie NEU! Details: https://example.test/a")
    second = listing_text_fingerprint("gaming pc", "wie neu details https://other.test/b")
    assert first == second
    assert normalize_listing_text("  RTX 4070S ", "TOP\nZustand") == "rtx 4070s top zustand"


def test_listing_text_similarity_detects_small_copy_edits_but_rejects_short_text() -> None:
    original = "Verkaufe meinen gepflegten Gaming PC mit Rechnung und vollständigem Zubehör wegen Umstieg."
    edited = "Verkaufe meinen sehr gepflegten Gaming PC mit Rechnung und vollständigem Zubehör wegen Umstieg."
    assert listing_text_similarity("RTX PC", original, "RTX PC", edited) >= 0.75
    assert listing_text_similarity("RTX PC", "Wie neu", "RTX PC", "Wie neu") == 0
