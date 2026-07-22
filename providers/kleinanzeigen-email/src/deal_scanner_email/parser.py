from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from typing import ClassVar
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field


class ParsedMail(BaseModel):
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    title: str | None = None
    price: str | None = None
    listing_url: str | None = None
    preview_image_url: str | None = None
    parser_version: str = "kleinanzeigen-mail-v1"
    raw_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    needs_recheck: bool = False


class KleinanzeigenMailParser:
    parser_version = "kleinanzeigen-mail-v1"
    listing_pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"https://(?:www\.)?kleinanzeigen\.de/s-anzeige/[^\s<>\"]+", re.I
    )
    price_pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"(?<!\d)(\d{1,3}(?:[. ]\d{3})*(?:,\d{2})?)\s*(?:€|EUR)\b", re.I
    )

    def __init__(self, allowed_senders: set[str]) -> None:
        self.allowed_senders = {sender.lower() for sender in allowed_senders}

    def parse(self, raw_message: bytes) -> ParsedMail:
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        sender = parseaddr(str(message.get("From", "")))[1].lower()
        sender_domain = sender.rpartition("@")[2]
        if not any(
            sender == allowed if "@" in allowed else sender_domain == allowed or sender_domain.endswith(f".{allowed}")
            for allowed in self.allowed_senders
        ):
            raise ValueError("email sender is not allowed")
        body, html = self._body(message)
        text = unescape(BeautifulSoup(html, "html.parser").get_text(" ") if html else body)
        url_match = self.listing_pattern.search(html or body)
        url = url_match.group(0) if url_match else None
        if url and urlparse(url).hostname not in {"kleinanzeigen.de", "www.kleinanzeigen.de"}:
            url = None
        price_match = self.price_pattern.search(text)
        subject = str(message.get("Subject", ""))
        date_header = str(message.get("Date", ""))
        try:
            received_at = parsedate_to_datetime(date_header) if date_header else datetime.now(UTC)
        except (TypeError, ValueError):
            received_at = datetime.now(UTC)
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=UTC)
        else:
            received_at = received_at.astimezone(UTC)
        title = subject.strip() or None
        image = self._first_image(html)
        return ParsedMail(
            message_id=str(message.get("Message-ID") or hashlib.sha256(raw_message).hexdigest()),
            sender=str(message.get("From", "")),
            subject=subject,
            received_at=received_at,
            title=title,
            price=price_match.group(1).replace(".", "").replace(",", ".") if price_match else None,
            listing_url=url,
            preview_image_url=image,
            raw_sha256=hashlib.sha256(raw_message).hexdigest(),
            needs_recheck=not bool(url and price_match),
        )

    @staticmethod
    def _body(message: EmailMessage) -> tuple[str, str]:
        plain = ""
        html = ""
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and not plain:
                plain = str(part.get_content())
            elif content_type == "text/html" and not html:
                html = str(part.get_content())
        return plain, html

    @staticmethod
    def _first_image(html: str) -> str | None:
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        for image in soup.find_all("img", src=True):
            src = str(image["src"])
            if src.startswith("https://"):
                return src
        return None
