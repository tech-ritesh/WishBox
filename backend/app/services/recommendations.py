"""Local gift recommendation engine (no external dependency).

Scores products against occasion / relationship / emotion / budget signals using
the real tags table. If WISHBOX_LLM_API_KEY is set, `llm_rerank` is the documented
hook to plug a Claude/OpenAI call in front of this (see docs/SCALABILITY.md).
"""
import re
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models
from app.core.config import settings

OCCASION_MAP = {
    "birthday": "birthday", "anniversary": "anniversary", "wedding": "wedding",
    "baby": "baby-shower", "diwali": "diwali", "holi": "holi", "rakhi": "raksha-bandhan",
    "raksha bandhan": "raksha-bandhan", "valentine": "valentines-day", "corporate": "corporate",
    "farewell": "farewell", "housewarming": "housewarming", "christmas": "christmas",
}
EMOTION_WORDS = ["romantic", "luxury", "funny", "emotional", "cute", "professional", "thoughtful"]
RELATIONSHIP_WORDS = ["wife", "husband", "mother", "mom", "father", "dad", "friend",
                      "colleague", "boss", "sister", "brother", "child"]


def parse_message(message: str) -> dict:
    text = (message or "").lower()
    parsed = {}
    m = re.search(r"(?:under|below|max|budget|₹|rs\.?|inr)?\s*(\d{3,6})", text)
    if m:
        parsed["budget"] = float(m.group(1))
    for key, slug in OCCASION_MAP.items():
        if key in text:
            parsed["occasion"] = slug
            break
    for w in EMOTION_WORDS:
        if w in text:
            parsed["emotion"] = w
            break
    for w in RELATIONSHIP_WORDS:
        if w in text:
            parsed["relationship"] = w
            break
    return parsed


def recommend(db: Session, occasion=None, relationship=None, emotion=None,
              budget: Optional[float] = None, limit: int = 8) -> List[models.Product]:
    products = db.query(models.Product).filter(models.Product.is_active.is_(True)).all()
    scored = []
    terms = {t.lower() for t in [occasion, relationship, emotion] if t}
    for p in products:
        if budget and float(p.effective_price) > budget:
            continue
        score = 0
        if budget:
            score += 2  # in budget
        haystack = f"{p.name} {p.description or ''}".lower()
        tag_names = {t.name.lower() for t in p.tags}
        for term in terms:
            if term in tag_names:
                score += 5
            elif term in haystack:
                score += 2
        score += float(p.rating_avg or 0)  # nudge by rating
        if score > 0 or not terms:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].id))
    results = [p for _, p in scored[:limit]]
    if not results:  # graceful fallback
        results = sorted(products, key=lambda p: float(p.effective_price))[:limit]
    return results


def build_message(occasion, relationship, emotion, budget, products) -> tuple[str, list]:
    tags = []
    if occasion:
        tags.append(occasion.replace("-", " ").title())
    if relationship:
        tags.append(f"for {relationship}")
    if emotion:
        tags.append(emotion.capitalize())
    if budget:
        tags.append(f"under ₹{int(budget):,}")
    context = ", ".join(tags) if tags else "your preferences"
    if not products:
        return ("I couldn't find a confident match — try widening the budget or describing the occasion.", tags)
    names = ", ".join(p.name for p in products[:3])
    msg = f"I curated {len(products)} options for {context}. Top picks: {names}."
    return msg, tags


def llm_rerank(query: str, products: List[models.Product]) -> Optional[List[models.Product]]:
    """Extension point: if an LLM key is configured, rerank/explain here.

    Intentionally returns None (local engine used) unless wired up — keeps WishBox
    fully local by default. See docs/SCALABILITY.md for the integration sketch.
    """
    if not settings.LLM_API_KEY:
        return None
    return None  # TODO: implement provider call when a key is supplied
