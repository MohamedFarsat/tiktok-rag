from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple
import re

from .url_utils import canonicalize_url

DISCLAIMER_TEXT = "Policies may change and enforcement depends on context."
ALLOWED_PLATFORMS = {"tiktok", "youtube", "instagram", "facebook"}


def format_response(question: str, grouped_evidence: Dict[str, List[Dict]]) -> Dict:
    """
    Build the stable /query response contract:
    {
      "question": str,
      "platforms": {
        "<platform_name>": {
          "answer": str,
          "citations": [
            {"page_title": str, "section_heading": str, "snippet": str, "url": str}
          ]
        }
      },
      "disclaimer": "Policies may change and enforcement depends on context."
    }
    """
    platforms: Dict[str, Dict] = {}
    for platform, evidence in (grouped_evidence or {}).items():
        platform_key = str(platform).lower()
        if platform_key not in ALLOWED_PLATFORMS:
            continue
        citations = _build_citations(evidence)
        if not citations:
            continue
        answer = _build_answer(platform_key, evidence, citations)
        platforms[platform_key] = {"answer": answer, "citations": citations}
    return {"question": question, "platforms": platforms, "disclaimer": DISCLAIMER_TEXT}


def validate_response(payload: Dict) -> None:
    required_top_keys = {"question", "platforms", "disclaimer"}
    if set(payload.keys()) != required_top_keys:
        raise ValueError("Response must contain only question, platforms, disclaimer.")
    if payload.get("disclaimer") != DISCLAIMER_TEXT:
        raise ValueError("Disclaimer is missing or incorrect.")
    if not isinstance(payload.get("question"), str):
        raise ValueError("Question must be a string.")
    platforms = payload.get("platforms")
    if not isinstance(platforms, dict):
        raise ValueError("Platforms must be an object.")
    for platform, platform_payload in platforms.items():
        if platform not in ALLOWED_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")
        if set(platform_payload.keys()) != {"answer", "citations"}:
            raise ValueError("Platform payload must contain only answer and citations.")
        if not isinstance(platform_payload.get("answer"), str):
            raise ValueError("Answer must be a string.")
        citations = platform_payload.get("citations")
        if not isinstance(citations, list):
            raise ValueError("Citations must be a list.")
        if len(citations) > 5:
            raise ValueError("Too many citations for a platform.")
        for citation in citations:
            if set(citation.keys()) != {
                "page_title",
                "section_heading",
                "snippet",
                "url",
            }:
                raise ValueError("Citation must contain page_title, section_heading, snippet, url.")
            if canonicalize_url(citation.get("url", "")) != citation.get("url", ""):
                raise ValueError("Citation URL is not canonical.")


def _build_citations(evidence: List[Dict]) -> List[Dict]:
    citations: List[Dict] = []
    seen: Set[Tuple[str, str]] = set()
    for item in evidence or []:
        page_title = _normalize_field(item.get("page_title"))
        section_heading = _normalize_field(item.get("heading"))
        snippet = _normalize_field(item.get("snippet"))
        url = canonicalize_url(_normalize_field(item.get("url")))
        key = (page_title, section_heading)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "page_title": page_title,
                "section_heading": section_heading,
                "snippet": snippet,
                "url": url,
            }
        )
        if len(citations) >= 5:
            break
    return citations


def _build_answer(platform: str, evidence: List[Dict], citations: List[Dict]) -> str:
    platform_name = _pretty_platform(platform)
    all_text = " ".join(
        _normalize_field(item.get("snippet"))
        + " "
        + _normalize_field(item.get("heading"))
        + " "
        + _normalize_field(item.get("page_title"))
        for item in evidence or []
    )
    procedural = _is_procedural(evidence)
    snippet_sentences = _select_snippet_sentences(
        [_normalize_field(item.get("snippet")) for item in evidence or []], limit=3
    )
    sentences: List[str] = []
    if procedural:
        sentences.append(
            f"The cited sections describe {platform_name} policy enforcement or review processes."
        )
        sentences.extend(snippet_sentences)
        if len(sentences) < 3:
            sentences.append(_section_summary_sentence(citations))
    else:
        policy_state = _classify_policy(all_text)
        sentences.append(
            f"Based on the cited policy sections, this content is {policy_state} on {platform_name}."
        )
        violations = _extract_violation_terms(all_text)
        if violations:
            sentences.append(
                "The cited sections mention common violations such as "
                + ", ".join(violations)
                + "."
            )
        sentences.extend(snippet_sentences[:2])
        if len(sentences) < 3:
            sentences.append(_section_summary_sentence(citations))
    sentences = [s for s in sentences if s]
    if len(sentences) < 3:
        extra = _select_snippet_sentences(
            [_normalize_field(item.get("snippet")) for item in evidence or []], limit=6
        )
        for sent in extra:
            if sent not in sentences:
                sentences.append(sent)
            if len(sentences) >= 3:
                break
    if len(sentences) < 3:
        list_sentence = _section_list_sentence(citations)
        if list_sentence and list_sentence not in sentences:
            sentences.append(list_sentence)
    sentences = sentences[:6]
    return " ".join(_ensure_sentence_end(s) for s in sentences)


def _pretty_platform(platform: str) -> str:
    mapping = {
        "tiktok": "TikTok",
        "youtube": "YouTube",
        "instagram": "Instagram",
        "facebook": "Facebook",
    }
    return mapping.get(platform, platform.title())


def _normalize_field(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _ensure_sentence_end(sentence: str) -> str:
    if not sentence:
        return sentence
    if sentence.endswith((".", "!", "?")):
        return sentence
    return sentence + "."


def _select_snippet_sentences(snippets: Iterable[str], limit: int = 2) -> List[str]:
    sentences: List[str] = []
    for snippet in snippets:
        for sentence in _split_sentences(snippet):
            cleaned = sentence.strip()
            if cleaned and cleaned not in sentences:
                sentences.append(cleaned)
            if len(sentences) >= limit:
                return sentences
    return sentences


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _classify_policy(text: str) -> str:
    lowered = text.lower()
    restricted = [
        "prohibit",
        "prohibited",
        "not allowed",
        "must not",
        "ban",
        "banned",
        "disallow",
        "removed",
        "restrict",
        "restricted",
    ]
    conditional = [
        "only",
        "must",
        "require",
        "allowed if",
        "may",
        "except",
        "unless",
        "limited",
        "age",
    ]
    if any(term in lowered for term in restricted):
        return "restricted"
    if any(term in lowered for term in conditional):
        return "conditionally allowed"
    return "generally allowed"


def _extract_violation_terms(text: str) -> List[str]:
    lowered = text.lower()
    terms = [
        ("violence", "violence"),
        ("hate", "hate"),
        ("harassment", "harassment"),
        ("bully", "bullying"),
        ("misinformation", "misinformation"),
        ("self-harm", "self-harm"),
        ("suicide", "self-harm"),
        ("sexual", "sexual content"),
        ("nudity", "nudity"),
        ("porn", "pornography"),
        ("drug", "drugs"),
        ("weapon", "weapons"),
        ("extremism", "extremism"),
        ("terrorism", "terrorism"),
        ("spam", "spam"),
        ("scam", "scams"),
    ]
    found: List[str] = []
    for needle, label in terms:
        if needle in lowered and label not in found:
            found.append(label)
    return found[:5]


def _is_procedural(evidence: List[Dict]) -> bool:
    keywords = [
        "appeal",
        "appeals",
        "enforcement",
        "strike",
        "strikes",
        "penalty",
        "penalties",
        "suspension",
        "termination",
        "account",
        "warning",
        "review process",
    ]
    for item in evidence or []:
        text = " ".join(
            [
                _normalize_field(item.get("page_title")),
                _normalize_field(item.get("heading")),
                _normalize_field(item.get("snippet")),
            ]
        ).lower()
        if any(keyword in text for keyword in keywords):
            return True
    return False


def _section_summary_sentence(citations: List[Dict]) -> str:
    if not citations:
        return ""
    first = citations[0]
    page_title = _normalize_field(first.get("page_title"))
    section = _normalize_field(first.get("section_heading"))
    if page_title and section:
        return f'Relevant sections include "{page_title}" - "{section}".'
    if page_title:
        return f'Relevant sections include "{page_title}".'
    return ""


def _section_list_sentence(citations: List[Dict]) -> str:
    if not citations:
        return ""
    items: List[str] = []
    for citation in citations[:2]:
        page_title = _normalize_field(citation.get("page_title"))
        section = _normalize_field(citation.get("section_heading"))
        if page_title and section:
            items.append(f"{page_title} - {section}")
        elif page_title:
            items.append(page_title)
    if not items:
        return ""
    return "Other cited sections include " + "; ".join(items) + "."
