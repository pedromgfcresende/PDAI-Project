import json
from datetime import date, datetime

import numpy as np
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

from agent_service.config import settings

load_dotenv()

psycopg2.extras.register_uuid()


def get_connection():
    conn = psycopg2.connect(settings.database_url)
    register_vector(conn)
    return conn


def insert_item(
    source: str,
    source_id: str,
    title: str,
    summary: str,
    url: str,
    authors: list[str],
    published_at: datetime | None,
    embedding: list[float] | None,
    raw_metadata: dict | None = None,
) -> int | None:
    """Insert an item, returning its id. Returns None if duplicate (source_id conflict)."""
    sql = """
        INSERT INTO items (source, source_id, title, summary, url, authors, published_at, embedding, raw_metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id) DO NOTHING
        RETURNING id
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (
            source, source_id, title, summary, url, authors,
            published_at, embedding,
            json.dumps(raw_metadata or {}),
        ))
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None


def update_item_scores(
    source_id: str,
    relevance_score: float,
    novelty_score: float,
    topics: list[str],
) -> None:
    sql = """
        UPDATE items
        SET relevance_score = %s, novelty_score = %s, topics = %s
        WHERE source_id = %s
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (relevance_score, novelty_score, topics, source_id))
        conn.commit()


def get_items_for_period(
    start: date,
    end: date,
    min_relevance: float = 0.5,
    limit: int = 200,
) -> list[dict]:
    sql = """
        SELECT id, source, source_id, title, summary, url, authors,
               published_at, relevance_score, novelty_score, topics
        FROM items
        WHERE published_at >= %s AND published_at < %s
          AND relevance_score >= %s
        ORDER BY relevance_score DESC, novelty_score DESC
        LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (start, end, min_relevance, limit))
        return [dict(row) for row in cur.fetchall()]


def get_unscored_items(limit: int = 100) -> list[dict]:
    sql = """
        SELECT id, source, source_id, title, summary, url, authors, published_at
        FROM items
        WHERE relevance_score IS NULL
        ORDER BY ingested_at DESC
        LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (limit,))
        return [dict(row) for row in cur.fetchall()]


def insert_report(
    report_type: str,
    title: str,
    content_md: str,
    period_start: date,
    period_end: date,
    content_html: str | None = None,
    quality_score: float | None = None,
    critic_feedback: dict | None = None,
    revision_count: int = 0,
    item_ids: list[int] | None = None,
) -> int:
    sql = """
        INSERT INTO reports (report_type, title, content_md, content_html, period_start, period_end,
                             quality_score, critic_feedback, revision_count, item_ids)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (
            report_type, title, content_md, content_html, period_start, period_end,
            quality_score, json.dumps(critic_feedback or {}),
            revision_count, item_ids or [],
        ))
        row = cur.fetchone()
        conn.commit()
        return row[0]


def get_latest_reports(report_type: str, limit: int = 10) -> list[dict]:
    sql = """
        SELECT id, report_type, title, content_md, content_html, period_start, period_end,
               quality_score, revision_count, published, created_at
        FROM reports
        WHERE report_type = %s
        ORDER BY period_start DESC
        LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (report_type, limit))
        return [dict(row) for row in cur.fetchall()]


def get_report_by_id(report_id: int) -> dict | None:
    sql = """
        SELECT id, report_type, title, content_md, content_html, period_start, period_end,
               quality_score, critic_feedback, revision_count, item_ids, published, created_at
        FROM reports
        WHERE id = %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (report_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_scored_item_count() -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM items WHERE relevance_score IS NOT NULL")
        return cur.fetchone()[0]


def get_signal_count() -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM signals WHERE active = TRUE")
        return cur.fetchone()[0]


def insert_signal(
    signal_type: str,
    topic: str,
    description: str,
    strength: float,
    evidence_ids: list[int],
) -> int:
    sql = """
        INSERT INTO signals (signal_type, topic, description, strength, evidence_ids)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (signal_type, topic, description, strength, evidence_ids))
        row = cur.fetchone()
        conn.commit()
        return row[0]


def get_active_signals() -> list[dict]:
    sql = """
        SELECT id, signal_type, topic, description, strength, evidence_ids,
               first_seen, last_updated
        FROM signals
        WHERE active = TRUE
        ORDER BY strength DESC
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]


def search_items_by_embedding(query_embedding: list[float], limit: int = 10) -> list[dict]:
    """Find items most similar to the query embedding using pgvector cosine distance."""
    vec = np.array(query_embedding, dtype=np.float32)
    sql = """
        SELECT id, source, title, summary, url, relevance_score, novelty_score, topics, published_at
        FROM items
        WHERE relevance_score IS NOT NULL AND embedding IS NOT NULL
        ORDER BY embedding <=> %s
        LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (vec, limit))
        return [dict(row) for row in cur.fetchall()]


def get_items_by_ids(item_ids: list[int]) -> list[dict]:
    """Fetch items by a list of IDs."""
    if not item_ids:
        return []
    sql = """
        SELECT id, source, title, summary, url, relevance_score, novelty_score, topics, published_at
        FROM items
        WHERE id = ANY(%s)
        ORDER BY relevance_score DESC
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (item_ids,))
        return [dict(row) for row in cur.fetchall()]


def get_signal_by_id(signal_id: int) -> dict | None:
    """Fetch a single signal by ID."""
    sql = """
        SELECT id, signal_type, topic, description, strength, evidence_ids,
               first_seen, last_updated
        FROM signals
        WHERE id = %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (signal_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_item_count() -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM items")
        return cur.fetchone()[0]


def get_report_count() -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM reports")
        return cur.fetchone()[0]
