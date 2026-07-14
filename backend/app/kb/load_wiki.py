"""
Load wiki/Chatbot markdown files into KB snippets table.
Run: py -m app.kb.load_wiki

Reads canonical pages from wiki/Chatbot/ and inserts structured snippets.
ponytail: add chunking strategy when pages grow > 500 tokens each; add then.
"""
import os, uuid, re, hashlib
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.db import engine, KBSnippet

VAULT_ROOT = Path(os.getenv("VAULT_ROOT", r"D:\2nd Brain\agent_wiki_cosmetic_clinic"))

# Map (relative path from vault root) → metadata defaults
FILE_META = {
    "project/Chatbot/Chatbot_Escalation_Boundary.md":           {"service": "general", "intent": "escalation",   "risk_level": "high",   "customer_visible": False},
    "project/Chatbot/Chatbot_FAQ_Hair_Transplant.md":            {"service": "hair",    "intent": "faq",           "risk_level": "low"},
    "project/Chatbot/Chatbot_FAQ_Facelift.md":                   {"service": "facelift","intent": "faq",           "risk_level": "low"},
    "wiki/Policy/Chinh_Sach_Khach_Hang_Quoc_Te_Pilot_V1.md":   {"service": "general", "intent": "policy",        "risk_level": "medium"},
    "wiki/Policy/Chinh_Sach_Hair_Transplant_Public.md":          {"service": "hair",    "intent": "policy_public", "risk_level": "low"},
    "wiki/Policy/Chinh_Sach_Facelift_Public.md":                 {"service": "facelift","intent": "policy_public", "risk_level": "low"},
    "wiki/Van_Hanh/Clinic_Facts_Quoc_Te.md":                    {"service": "general", "intent": "ops_facts",     "risk_level": "low"},
    "wiki/Policy/Policy_Booking_Deposit_Payment.md":             {"service": "general", "intent": "booking",       "risk_level": "medium"},
    "wiki/Policy/Policy_Cancellation_Refund_Revision.md":        {"service": "general", "intent": "refund",        "risk_level": "medium"},
}


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown by ## headings. Returns list of (heading, body)."""
    parts = re.split(r'^(##[^#].*?)$', text, flags=re.MULTILINE)
    sections = []
    intro = parts[0].strip()
    if intro:
        sections.append(("intro", intro))
    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].strip("# ").strip()
        body = parts[i + 1].strip()
        if body:
            sections.append((heading, body))
    return sections


def load():
    if not VAULT_ROOT.exists():
        print(f"Vault path not found: {VAULT_ROOT}")
        return

    loaded = 0
    with Session(engine) as db:
        for rel_path, meta in FILE_META.items():
            fpath = VAULT_ROOT / rel_path
            if not fpath.exists():
                print(f"  SKIP (not found): {rel_path}")
                continue

            raw = fpath.read_text(encoding="utf-8")
            # Strip YAML frontmatter
            if raw.startswith("---"):
                raw = re.sub(r'^---.*?---\s*', '', raw, flags=re.DOTALL)

            sections = _split_sections(raw)
            for heading, body in sections:
                content_hash = hashlib.md5(body.encode()).hexdigest()[:8]
                stem = Path(rel_path).stem
                sid = f"{stem}__{re.sub(r'\\W+','_', heading)}__{content_hash}"
                existing = db.query(KBSnippet).filter_by(snippet_id=sid).first()
                if existing:
                    # update if text changed
                    old_hash = hashlib.md5(existing.answer_text.encode()).hexdigest()[:8]
                    if old_hash == content_hash:
                        continue
                    existing.answer_text = body
                    existing.title = heading
                else:
                    db.add(KBSnippet(
                        id=str(uuid.uuid4()),
                        snippet_id=sid,
                        source_path=rel_path,
                        source_section=heading,
                        title=f"{Path(rel_path).stem} — {heading}",
                        language="vi",
                        answer_text=body,
                        is_active=True,
                        customer_visible=meta.get("customer_visible", True),
                        **{k: v for k, v in meta.items() if k != "customer_visible"},
                    ))
                loaded += 1
        db.commit()
    print(f"KB load done: {loaded} snippets upserted from {VAULT_ROOT}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parents[3] / ".env")
    from app.models.db import init_db
    from app.services.kb_service import setup_fts
    init_db()
    load()
    setup_fts()
    print("FTS index rebuilt.")
