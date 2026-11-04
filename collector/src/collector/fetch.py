"""Download resiliente de feeds (timeouts, retries com backoff, User-Agent)."""

from __future__ import annotations

import logging
from typing import Any

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; PainelPessoalTrendBot/1.0; "
    "+https://github.com/marialuizabustani/painel_pessoal)"
)
TIMEOUT = (10, 25)  # (connect, read) em segundos
MAX_BYTES = 8 * 1024 * 1024


class FeedError(RuntimeError):
    pass


def build_session() -> requests.Session:
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    session.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8,pt-BR;q=0.7",
        }
    )
    return session


def fetch_feed(session: requests.Session, url: str) -> list[Any]:
    try:
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FeedError(f"HTTP error: {exc}") from exc
    if len(resp.content) > MAX_BYTES:
        raise FeedError(f"feed too large ({len(resp.content)} bytes)")

    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        raise FeedError(f"invalid feed: {parsed.get('bozo_exception')!r}")
    return list(parsed.entries)
