"""Conversão de entradas de feed (feedparser) em ``Article`` normalizado."""

from __future__ import annotations

import calendar
import html
import re
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

from .sources import Source

# Resumos curtos (ex.: só uma URL) disparam este aviso inofensivo do BeautifulSoup.
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|mc_cid$|mc_eid$|ref$|cmpid$|ncid$)", re.I)
_MAX_SUMMARY = 600


@dataclass(slots=True)
class Article:
    url: str
    title: str
    summary: str
    image_url: str | None
    author: str | None
    publisher: str | None
    language: str
    published_at: datetime | None


def clean_url(url: str) -> str | None:
    """Remove parâmetros de rastreamento e fragmento; aceita só http(s)."""
    url = (url or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING_PARAMS.match(k)])
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, query, ""))


def html_to_text(raw: str, limit: int = _MAX_SUMMARY) -> str:
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    if len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return text


def _first_img(raw: str) -> str | None:
    if not raw or "<img" not in raw:
        return None
    img = BeautifulSoup(raw, "html.parser").find("img")
    return img.get("src") if img else None


def extract_image(entry: Any) -> str | None:
    candidates: list[str | None] = []
    for key in ("media_content", "media_thumbnail"):
        for media in entry.get(key) or []:
            candidates.append(media.get("url"))
    for enc in entry.get("enclosures") or []:
        if str(enc.get("type", "")).startswith("image/"):
            candidates.append(enc.get("href") or enc.get("url"))
    for content in entry.get("content") or []:
        candidates.append(_first_img(content.get("value", "")))
    candidates.append(_first_img(entry.get("summary", "")))
    for c in candidates:
        if c and (u := clean_url(c)):
            return u
    return None


def parse_date(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime.fromtimestamp(calendar.timegm(st), tz=UTC)
            except (OverflowError, ValueError, TypeError):
                continue
    return None


def _split_google_title(title: str) -> tuple[str, str | None]:
    """Google News formata títulos como 'Manchete - Veículo'."""
    if " - " in title:
        head, tail = title.rsplit(" - ", 1)
        if head and 0 < len(tail) <= 60:
            return head.strip(), tail.strip()
    return title, None


def entry_to_article(entry: Any, source: Source) -> Article | None:
    url = clean_url(entry.get("link", ""))
    title = html_to_text(entry.get("title", ""), limit=300)
    if not url or not title:
        return None

    publisher: str | None = None
    summary_raw = entry.get("summary", "")
    if source.kind == "google_news":
        title, publisher = _split_google_title(title)
        src = entry.get("source") or {}
        publisher = (src.get("title") if hasattr(src, "get") else None) or publisher
        # O resumo do Google News apenas repete título + veículo.
        summary = ""
    else:
        content = (entry.get("content") or [{}])[0].get("value", "")
        summary = html_to_text(summary_raw or content)

    return Article(
        url=url,
        title=title,
        summary=summary,
        image_url=extract_image(entry),
        author=(entry.get("author") or None),
        publisher=publisher,
        language=source.language,
        published_at=parse_date(entry),
    )
