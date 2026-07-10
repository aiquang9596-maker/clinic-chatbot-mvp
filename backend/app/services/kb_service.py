"""Knowledge base retrieval — SQLite FTS5 + metadata filter."""
import sqlite3, os, logging

log = logging.getLogger(__name__)
DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./data/chatbot.db").replace("sqlite:///", "")


def retrieve(query: str, intent: str, service: str = None, top_k: int = 4) -> list[dict]:
    """Return top-k KB snippets relevant to the query + intent."""
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # Build FTS search over answer_text + title
        # ponytail: add vector embeddings (Chroma) when FTS recall is insufficient
        params = [query, query]
        service_clause = ""
        if service and service not in ("unknown", None):
            service_clause = "AND (service = ? OR service = 'general')"
            params.append(service)

        rows = cur.execute(f"""
            SELECT k.snippet_id, k.title, k.source_path, k.answer_text,
                   k.risk_level, k.service, k.intent
            FROM kb_snippets k
            JOIN kb_snippets_fts fts ON fts.rowid = k.rowid
            WHERE kb_snippets_fts MATCH ?
              AND k.is_active = 1
              AND k.customer_visible = 1
              AND k.risk_level IN ('low', 'medium')
              {service_clause}
            ORDER BY rank
            LIMIT ?
        """, [*params[:1], *([service] if service_clause else []), top_k]).fetchall()

        return [dict(r) for r in rows]
    except Exception as e:
        log.error("KB retrieve failed: %s", e)
        return []


def setup_fts(db_path: str = None):
    """Create FTS5 virtual table if missing. Run once at startup."""
    path = db_path or DB_PATH
    con = sqlite3.connect(path)
    con.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS kb_snippets_fts
        USING fts5(title, answer_text, content='kb_snippets', content_rowid='rowid')
    """)
    con.execute("""
        INSERT OR IGNORE INTO kb_snippets_fts(kb_snippets_fts) VALUES('rebuild')
    """)
    con.commit()
    con.close()
