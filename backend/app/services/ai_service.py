"""AI classification and draft reply via local Ollama."""
import os, httpx, logging, json, re

# ponytail: parser strips code fences / trailing junk from small local models; replace with stricter model when quality grows

log = logging.getLogger(__name__)
OLLAMA_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")

# ponytail: swap to cloud fallback (Claude/Gemini) when quality insufficient; add when needed


def _chat(system: str, user: str, timeout: int = 30) -> str:
    """Single-turn Ollama /api/chat call."""
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]
    except Exception as e:
        log.error("Ollama call failed: %s", e)
        return ""


def _parse_jsonish(raw: str) -> dict:
    """Best-effort JSON extraction for local models that wrap output in fences or append junk."""
    if not raw:
        raise ValueError("empty model output")
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end+1]
    return json.loads(raw)


def classify(text: str, history: list) -> tuple[str, str]:
    """Return (intent, risk_level). Fallback to (unknown, medium) on error."""
    system = """You are a message classifier for a medical tourism clinic chatbot.
Return JSON only: {"intent": "<slug>", "risk_level": "low|medium|high|emergency"}

Risk rules (hard):
- emergency: post-op abnormal symptoms, breathing difficulty, severe pain, heavy bleeding
- high: medical candidacy, drug/medication, complications, complaint/refund, guarantee, final price
- medium: clinical procedure questions, revision requests, post-op general
- low: greeting, general info, booking process, hours, location, photos request

Intent slugs (examples): greeting, general_info, service_inquiry_hair, service_inquiry_facelift,
candidacy_question, medical_question, pricing_inquiry, booking_process, cancellation_refund,
complaint, post_op_question, emergency, unknown
"""
    snippet = "\n".join([f"[{m.direction}] {m.content_text}" for m in history[-5:]])
    user = f"History:\n{snippet}\n\nNew message: {text}"
    raw = _chat(system, user)
    try:
        data = _parse_jsonish(raw)
        return data.get("intent", "unknown"), data.get("risk_level", "medium")
    except Exception:
        return "unknown", "medium"


def draft_reply(text: str, history: list, sources: list) -> tuple[str, float]:
    """Return (draft_text, confidence 0-1). Returns ('', 0.0) on error."""
    kb_block = "\n\n".join(
        f"[{s['snippet_id']}] {s['title']}\n{s['answer_text']}"
        for s in (sources or [])
    ) or "No KB context available."

    system = """You are an AI copilot for a clinic coordinator. Write a SHORT, safe, polite customer-facing reply.

RULES (hard):
- Use ONLY the KB snippets provided. Do NOT invent facts, prices, guarantees, or clinical assessments.
- If KB is insufficient, say a coordinator will follow up.
- Do NOT diagnose. Do NOT assess candidacy. Do NOT commit to final price. Do NOT promise outcomes.
- If any medical red flag exists, say "a coordinator will reach out shortly" and nothing more.
- Reply in the same language the customer wrote in (English or Vietnamese).

Return JSON only: {"reply": "<text>", "confidence": <0.0-1.0>, "handoff_reason": "<or null>"}
"""
    snippet = "\n".join([f"[{m.direction}] {m.content_text}" for m in history[-5:]])
    user = f"KB:\n{kb_block}\n\nHistory:\n{snippet}\n\nCustomer: {text}"
    raw = _chat(system, user, timeout=45)
    try:
        data = _parse_jsonish(raw)
        return data.get("reply", ""), float(data.get("confidence", 0.0))
    except Exception:
        return "", 0.0


def _detect_lang(text: str) -> str:
    return "vi" if any(c in (text or "") for c in "àáãạảăắằẳẵặèéẹẻẽêềếểễệđìíĩỉịòóõọỏôốồổỗộơớờởỡợùúũụủừứữựỳỹỷỵ") else "en"


def _fallback_options(text: str, instruction: str = ""):
    if instruction.strip():
        notes = f"Local model phi3:mini is too small for reliable rewrite. Safe templates shown. Instruction recorded: {instruction.strip()}"
    else:
        notes = "Local model phi3:mini is too small for reliable suggestions. Showing safe template options."
    return {
        "options": [
            {"id": 1, "label": "Safe — acknowledge", "text": "Cảm ơn bạn đã nhắn tin. Một tư vấn viên sẽ liên hệ bạn sớm nhất có thể." if _detect_lang(text) == "vi" else "Thank you for reaching out. A coordinator will get back to you shortly."},
            {"id": 2, "label": "Warm — ask for info", "text": "Chào bạn! Để hỗ trợ tốt hơn, bạn có thể chia sẻ thêm thông tin về dịch vụ bạn quan tâm không ạ?" if _detect_lang(text) == "vi" else "Hello! To better assist you, could you share which service you're interested in?"},
            {"id": 3, "label": "Professional — next step", "text": "Cảm ơn bạn. Đội ngũ tư vấn sẽ phản hồi bạn trong thời gian sớm nhất. Nếu cần gấp, vui lòng gọi hotline của clinic." if _detect_lang(text) == "vi" else "Thank you. Our team will respond as soon as possible. For urgent matters, please contact our clinic hotline."},
        ],
        "notes": notes,
        "confidence": 0.3,
        "risk_level": "low",
    }


def suggest_options(history: list, sources: list, instruction: str = "") -> dict:
    """Return 1-3 safe reply options + metadata for the operator panel."""
    latest_customer = next(
        (m.content_text for m in reversed(history)
         if m.direction == "inbound" and m.content_text),
        ""
    )
    # ponytail: phi3:mini is too small for reliable suggestion generation.
    # Use safe templates by default; enable AI generation when you switch to
    # a 7B+ model (e.g. llama3.2, mistral) or cloud API.
    return _fallback_options(latest_customer, instruction)
