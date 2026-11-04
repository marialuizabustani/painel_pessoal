"""Persistência no Postgres (Supabase) via psycopg 3.

O pooler do Supabase na porta 6543 opera em *transaction mode*, que não suporta
prepared statements — por isso ``prepare_threshold=None``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field

import psycopg

from .classifier import Classification
from .parsing import Article
from .sources import Source


@dataclass
class RunStats:
    feeds_total: int = 0
    feeds_failed: int = 0
    articles_seen: int = 0
    articles_inserted: int = 0
    articles_updated: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.feeds_total and self.feeds_failed == self.feeds_total:
            return "failed"
        return "partial" if self.feeds_failed else "success"


def connect(dsn: str) -> psycopg.Connection:
    # autocommit: cada ``conn.transaction()`` vira uma transação real e independente.
    return psycopg.connect(
        dsn,
        autocommit=True,
        prepare_threshold=None,
        connect_timeout=20,
        application_name="trend-collector",
    )


def start_run(conn: psycopg.Connection, run_url: str | None) -> int:
    with conn.transaction():
        row = conn.execute(
            "insert into public.ingestion_runs (run_url) values (%s) returning id", (run_url,)
        ).fetchone()
    return int(row[0])


def finish_run(conn: psycopg.Connection, run_id: int, stats: RunStats) -> None:
    with conn.transaction():
        conn.execute(
            """
            update public.ingestion_runs
               set finished_at = now(), status = %s, feeds_total = %s, feeds_failed = %s,
                   articles_seen = %s, articles_inserted = %s, articles_updated = %s,
                   errors = %s::jsonb
             where id = %s
            """,
            (
                stats.status,
                stats.feeds_total,
                stats.feeds_failed,
                stats.articles_seen,
                stats.articles_inserted,
                stats.articles_updated,
                json.dumps(stats.errors[:200], ensure_ascii=False),
                run_id,
            ),
        )


def upsert_sources(conn: psycopg.Connection, sources: Iterable[Source]) -> dict[str, int]:
    ids: dict[str, int] = {}
    with conn.transaction():
        for s in sources:
            row = conn.execute(
                """
                insert into public.sources (slug, name, site_url, feed_url, language, kind, is_curated)
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (slug) do update
                   set name = excluded.name, site_url = excluded.site_url,
                       feed_url = excluded.feed_url, language = excluded.language,
                       kind = excluded.kind, is_curated = excluded.is_curated
                returning id
                """,
                (s.slug, s.name, s.site_url, s.feed_url, s.language, s.kind, s.curated),
            ).fetchone()
            ids[s.slug] = int(row[0])
    return ids


def topic_ids(conn: psycopg.Connection) -> dict[str, int]:
    return {slug: int(i) for i, slug in conn.execute("select id, slug from public.topics")}


def save_articles(
    conn: psycopg.Connection,
    source_id: int,
    items: Iterable[tuple[Article, Classification]],
    topics: dict[str, int],
    stats: RunStats,
) -> None:
    """Upsert idempotente: reexecuções no mesmo dia não duplicam registros."""
    with conn.transaction():
        for art, cls in items:
            row = conn.execute(
                """
                insert into public.articles
                    (source_id, url, title, summary, image_url, author, publisher,
                     language, published_at, relevance_score)
                values (%s, %s, %s, nullif(%s, ''), %s, %s, %s, %s, %s, %s)
                on conflict (url) do update
                   set title = excluded.title,
                       summary = coalesce(excluded.summary, public.articles.summary),
                       image_url = coalesce(excluded.image_url, public.articles.image_url),
                       relevance_score = greatest(excluded.relevance_score,
                                                  public.articles.relevance_score)
                returning id, (xmax = 0) as inserted
                """,
                (
                    source_id,
                    art.url,
                    art.title,
                    art.summary,
                    art.image_url,
                    (art.author or None) and art.author[:200],
                    art.publisher,
                    art.language,
                    art.published_at,
                    cls.score,
                ),
            ).fetchone()
            article_id, inserted = int(row[0]), bool(row[1])
            if inserted:
                stats.articles_inserted += 1
            else:
                stats.articles_updated += 1

            for slug, score in cls.topics.items():
                if slug in topics:
                    conn.execute(
                        """
                        insert into public.article_topics (article_id, topic_id, score)
                        values (%s, %s, %s)
                        on conflict (article_id, topic_id)
                        do update set score = greatest(excluded.score, public.article_topics.score)
                        """,
                        (article_id, topics[slug], score),
                    )
