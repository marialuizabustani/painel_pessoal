"""Ponto de entrada do pipeline: ``python -m collector.main``.

Variáveis de ambiente:
  SUPABASE_DB_URL   (obrigatória) DSN Postgres do Supabase.
  LOOKBACK_HOURS    janela de publicação aceita (padrão: 48).
  MAX_PER_FEED      máximo de itens por feed (padrão: 40).
  DRY_RUN=1         coleta e classifica sem gravar no banco.
  GITHUB_RUN_URL    link da execução (preenchido pelo workflow).
"""

from __future__ import annotations

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

import psycopg

from .classifier import Classification, classify, is_relevant
from .db import RunStats, connect, finish_run, save_articles, start_run, topic_ids, upsert_sources
from .fetch import FeedError, build_session, fetch_feed
from .parsing import Article, entry_to_article
from .sources import Source, all_sources

log = logging.getLogger("collector")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def collect_source(
    session, source: Source, since: datetime, max_items: int
) -> list[tuple[Article, Classification]]:
    entries = fetch_feed(session, source.feed_url)[:max_items]
    out: list[tuple[Article, Classification]] = []
    for entry in entries:
        art = entry_to_article(entry, source)
        if art is None:
            continue
        if art.published_at and art.published_at < since:
            continue
        cls = classify(art.title, art.summary, source.default_topic)
        if is_relevant(cls, curated=source.curated, has_default=source.default_topic is not None):
            out.append((art, cls))
    return out


def run() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    dry_run = os.environ.get("DRY_RUN") == "1"
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn and not dry_run:
        log.error("SUPABASE_DB_URL não definido.")
        return 2

    since = datetime.now(UTC) - timedelta(hours=_env_int("LOOKBACK_HOURS", 48))
    max_items = _env_int("MAX_PER_FEED", 40)
    sources = all_sources()
    stats = RunStats(feeds_total=len(sources))
    session = build_session()

    results: dict[str, list[tuple[Article, Classification]]] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(collect_source, session, s, since, max_items): s for s in sources}
        for fut in as_completed(futures):
            src = futures[fut]
            try:
                results[src.slug] = fut.result()
                log.info("%-40s %3d relevantes", src.slug, len(results[src.slug]))
            except FeedError as exc:
                stats.feeds_failed += 1
                stats.errors.append({"source": src.slug, "error": str(exc)[:500]})
                log.warning("%-40s FALHOU: %s", src.slug, exc)
            except Exception as exc:  # noqa: BLE001 — uma fonte nunca derruba o pipeline
                stats.feeds_failed += 1
                stats.errors.append({"source": src.slug, "error": repr(exc)[:500]})
                log.exception("%-40s erro inesperado", src.slug)

    # Deduplicação entre fontes (mesma URL em feeds diferentes).
    seen: set[str] = set()
    for slug, items in results.items():
        unique = []
        for art, cls in items:
            if art.url not in seen:
                seen.add(art.url)
                unique.append((art, cls))
        results[slug] = unique
        stats.articles_seen += len(unique)

    if dry_run:
        log.info("DRY_RUN: %d matérias relevantes; nada gravado.", stats.articles_seen)
        return 0

    with connect(dsn) as conn:
        run_id = start_run(conn, os.environ.get("GITHUB_RUN_URL"))
        try:
            source_ids = upsert_sources(conn, sources)
            topics = topic_ids(conn)
        except psycopg.Error as exc:
            stats.errors.append({"source": "database", "error": repr(exc)[:500]})
            stats.feeds_failed = stats.feeds_total
            finish_run(conn, run_id, stats)
            raise
        for slug, items in results.items():
            if not items:
                continue
            try:  # uma transação por fonte: falha isolada não perde o restante
                save_articles(conn, source_ids[slug], items, topics, stats)
            except psycopg.Error as exc:
                stats.feeds_failed += 1
                stats.errors.append({"source": slug, "error": f"db: {exc!r}"[:500]})
                log.error("%-40s erro ao gravar: %s", slug, exc)
        finish_run(conn, run_id, stats)

    log.info(
        "Concluído [%s]: %d fontes (%d falharam), %d vistas, %d novas, %d atualizadas.",
        stats.status,
        stats.feeds_total,
        stats.feeds_failed,
        stats.articles_seen,
        stats.articles_inserted,
        stats.articles_updated,
    )
    return 1 if stats.status == "failed" else 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
