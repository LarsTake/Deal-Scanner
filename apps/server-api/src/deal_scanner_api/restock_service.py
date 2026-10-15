from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException

SHOP_HOSTS = {"www.otto.de", "www.mediamarkt.de", "www.saturn.de", "www.amazon.de", "www.mueller.de"}


def validate_shop_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc not in SHOP_HOSTS
        or len(parsed.path) <= 1
        or parsed.username
        or parsed.password
    ):
        raise HTTPException(status_code=422, detail="restock requires an HTTPS product URL from a supported shop")


class _ProductData(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_json = False
        self.buffer: list[str] = []
        self.documents: list[Any] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script" and values.get("type") == "application/ld+json":
            self.in_json = True
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.in_json:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_json:
            self.in_json = False
            try:
                self.documents.append(json.loads("".join(self.buffer)))
            except ValueError:
                pass


def parse_availability(html: str, url: str) -> tuple[bool | None, str]:
    parser = _ProductData()
    parser.feed(html)
    products: list[dict[str, Any]] = []

    def collect(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            types = value.get("@type", [])
            if types == "Product" or isinstance(types, list) and "Product" in types:
                products.append(value)
            collect(value.get("@graph", []))

    for document in parser.documents:
        collect(document)
    target = urlsplit(url)
    matching = [
        item
        for item in products
        if (
            lambda candidate: (
                candidate.netloc == target.netloc and candidate.path.rstrip("/") == target.path.rstrip("/")
            )
        )(urlsplit(str(item.get("url") or item.get("@id") or "")))
    ]
    if not matching and len(products) == 1 and not products[0].get("url"):
        matching = products
    if len(matching) != 1:
        return None, "Verfügbarkeit nicht eindeutig erkannt"
    product = matching[0]
    offers = product.get("offers", [])
    offers = offers if isinstance(offers, list) else [offers]
    states = [str(item.get("availability", "")).rsplit("/", 1)[-1] for item in offers if isinstance(item, dict)]
    name = str(product.get("name") or "Produkt")[:500]
    if "InStock" in states:
        return True, name
    if states and all(state in {"OutOfStock", "SoldOut", "Discontinued"} for state in states):
        return False, name
    return None, name
