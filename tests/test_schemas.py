from deal_scanner_api.schemas import ManualImportRequest


def test_manual_import_accepts_normalized_universal_platform() -> None:
    payload = ManualImportRequest.model_validate(
        {
            "platform": "shop-example",
            "externalId": "page-1234",
            "url": "https://shop.example/offers/page-1234",
            "title": "Universal import fixture",
            "price": "42.00",
            "currency": "EUR",
            "categoryProfile": "general",
        }
    )

    assert payload.platform == "shop-example"
