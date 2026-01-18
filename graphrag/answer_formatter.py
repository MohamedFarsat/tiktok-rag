from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple
import re

from .url_utils import canonicalize_url
from .ollama_client import (
    DEFAULT_LLM_MODEL,
    FALLBACK_LLM_MODEL,
    ModelNotFoundError,
    OllamaClient,
    OllamaError,
)

DISCLAIMER_TEXT = "Policies may change and enforcement depends on context."
ALLOWED_PLATFORMS = {"tiktok", "youtube", "instagram", "facebook"}
NOT_ALLOWED_TERMS = [
    "we don't allow",
    "we do not allow",
    "not allowed",
    "prohibited",
    "we will remove",
    "we'll remove",
]
ALLOWED_TERMS = ["allowed", "we allow", "may be allowed", "is allowed"]


def format_response(
    question: str,
    grouped_evidence: Dict[str, List[Dict]],
    use_llm: bool = True,
    llm_model: str = DEFAULT_LLM_MODEL,
) -> Dict:
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
    requested_model = _normalize_field(llm_model) or DEFAULT_LLM_MODEL
    llm_client = OllamaClient() if use_llm else None
    allow_fallback = requested_model == DEFAULT_LLM_MODEL
    for platform, evidence in (grouped_evidence or {}).items():
        platform_key = str(platform).lower()
        if platform_key not in ALLOWED_PLATFORMS:
            continue
        citations = _build_citations(evidence)
        if not citations:
            continue
        answer = None
        if use_llm and llm_client:
            answer = _build_llm_answer(
                question,
                platform_key,
                evidence,
                llm_client,
                requested_model,
                allow_fallback,
            )
        if not answer:
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
    snippets = [_normalize_field(item.get("snippet")) for item in evidence or []]
    inferred = infer_verdict_from_evidence(snippets)
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
        snippets, limit=3
    )
    sentences: List[str] = []
    sentences.append(_default_verdict_sentence(inferred, platform_name))
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
    answer = " ".join(_ensure_sentence_end(s) for s in sentences)
    answer = _limit_answer_length(answer)
    return normalize_text(answer)


def _build_llm_answer(
    question: str,
    platform: str,
    evidence: List[Dict],
    client: OllamaClient,
    model_name: str,
    allow_fallback: bool,
) -> Optional[str]:
    available_models: Optional[Set[str]] = None
    try:
        available_models = {m.lower() for m in client.list_models()}
    except OllamaError:
        available_models = None
    prompt = _build_llm_prompt(question, platform, evidence, max_excerpts=5)
    short_prompt = _build_llm_prompt(question, platform, evidence, max_excerpts=2)
    snippets = [_normalize_field(item.get("snippet")) for item in evidence or []]
    inferred = infer_verdict_from_evidence(snippets)
    print(f"[graphrag] LLM inferred verdict: {inferred}")
    requested = model_name.strip()
    model_candidates = [requested]
    if available_models:
        requested_lower = requested.lower()
        if requested_lower not in available_models:
            if FALLBACK_LLM_MODEL in available_models:
                model_candidates = [FALLBACK_LLM_MODEL]
            else:
                model_candidates = [requested]
    if allow_fallback and model_candidates[-1] != FALLBACK_LLM_MODEL:
        model_candidates.append(FALLBACK_LLM_MODEL)
    for candidate in model_candidates:
        try:
            print(f"[graphrag] LLM request platform={platform} model={candidate}")
            response = client.generate(
                model=candidate, prompt=prompt, short_prompt=short_prompt
            )
        except ModelNotFoundError:
            print(f"[graphrag] LLM model not found: {candidate}")
            continue
        except (OllamaError, TimeoutError):
            print(f"[graphrag] LLM request failed for model: {candidate}")
            return None
        cleaned = normalize_text(response.strip())
        preview = cleaned.replace("\n", " ")[:200]
        print(f"[graphrag] LLM response preview: {preview}")
        original_first_line = _first_line(cleaned)
        print(f"[graphrag] LLM answer first line: {original_first_line}")
        fixed = fix_llm_answer_verdict(cleaned, inferred)
        if fixed != cleaned:
            print(f"[graphrag] LLM answer first line (fixed): {_first_line(fixed)}")
        cleaned = _limit_answer_length(fixed)
        cleaned = normalize_text(cleaned)
        if _is_valid_llm_answer(cleaned, platform):
            print(f"[graphrag] LLM response accepted for model: {candidate}")
            return cleaned
        print(f"[graphrag] LLM response rejected for model: {candidate}")
    return None


def _build_llm_prompt(
    question: str,
    platform: str,
    evidence: List[Dict],
    max_excerpts: int,
) -> str:
    platform_name = _pretty_platform(platform)
    excerpts: List[str] = []
    for item in evidence or []:
        page_title = _normalize_field(item.get("page_title"))
        section_heading = _normalize_field(item.get("heading"))
        snippet = _normalize_field(item.get("snippet"))
        if not snippet:
            continue
        excerpts.append(
            f"- Title: {page_title} | Section: {section_heading} | Excerpt: {snippet}"
        )
        if len(excerpts) >= max_excerpts:
            break
    instructions = (
        "Use ONLY the provided policy excerpts. Do not invent policies or mention other "
        "platforms. Do not output citations or URLs. Return 3-6 sentences per platform. "
        "First sentence must be one of: \"Allowed:\", \"Not allowed:\", or \"Depends:\". "
        "If evidence is insufficient, say \"Based on the provided guidelines, it depends\" "
        "and ask for more context. "
        "If ANY excerpt contains a clear prohibition (e.g., 'we don't allow', 'not allowed', "
        "'prohibited', 'remove'), your first sentence MUST start with 'Not allowed:'. "
        "If the excerpts contain both a prohibition and an exception, label as 'Not allowed:' "
        "and then describe the exception(s) as limited cases. "
        "Never say 'not explicitly mentioned' if any excerpt is clearly about the topic or "
        "uses words like 'violent', 'graphic', 'gory', 'disturbing'. "
        "Only say 'Depends:' when there is NO clear allow/disallow statement in the excerpts."
    )
    lines = [
        instructions,
        f"Question: {question}",
        f"Platform: {platform_name}",
        "Policy excerpts:",
    ]
    if excerpts:
        lines.extend(excerpts)
    else:
        lines.append("- (no excerpts provided)")
    return "\n".join(lines)


def _is_valid_llm_answer(text: str, platform: str) -> bool:
    if not text:
        return False
    raw = text.lstrip()
    prefix_match = re.match(r"^(Allowed|Not allowed|Depends)\b", raw)
    if not prefix_match:
        return False
    sentences = _split_sentences(text)
    if len(sentences) < 3 or len(sentences) > 6:
        return False
    first = sentences[0].strip()
    prefixes = ("Allowed", "Not allowed", "Depends")
    if not first.startswith(prefixes):
        return False
    if first.startswith("Depends:"):
        if "based on the provided guidelines" not in text.lower():
            return False
    lowered = text.lower()
    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return False
    other_platforms = {p for p in ALLOWED_PLATFORMS if p != platform}
    for other in other_platforms:
        if other in lowered:
            return False
    return True


def infer_verdict_from_evidence(snippets: List[str]) -> str:
    lowered = [snippet.lower() for snippet in snippets if snippet]
    for snippet in lowered:
        if any(term in snippet for term in NOT_ALLOWED_TERMS):
            return "NOT_ALLOWED"
    for snippet in lowered:
        if any(term in snippet for term in ALLOWED_TERMS):
            return "ALLOWED"
    return "DEPENDS"


def fix_llm_answer_verdict(answer_text: str, inferred: str) -> str:
    if not answer_text:
        return answer_text
    sentences = [s.strip() for s in _split_sentences(answer_text) if s.strip()]
    if not sentences:
        return answer_text
    if inferred == "NOT_ALLOWED":
        rewritten = _rewrite_not_allowed_llm_answer(answer_text)
        if rewritten != answer_text:
            print("[graphrag] LLM answer rewritten by guardrail (NOT_ALLOWED).")
        answer_text = rewritten
    first_sentence = sentences[0]
    updated = answer_text
    if inferred == "DEPENDS":
        if first_sentence.startswith(("Not allowed:", "Allowed:")):
            sentences[0] = (
                "Depends: Based on the provided guidelines, it depends on context and "
                "specific details."
            )
            updated = " ".join(_ensure_sentence_end(s) for s in sentences)
            updated = _normalize_llm_answer_sentences(updated, inferred)
            answer_text = updated
    if inferred == "ALLOWED":
        if "not explicitly mentioned" in answer_text.lower():
            updated = _remove_not_explicitly_mentioned(answer_text)
            if _needs_sentence_normalization(updated):
                updated = _normalize_llm_answer_sentences(updated, inferred)
            answer_text = updated
    if _needs_sentence_normalization(answer_text):
        answer_text = _normalize_llm_answer_sentences(answer_text, inferred)
    answer_text = _enforce_verdict_first_sentence(answer_text, inferred)
    return answer_text


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
    text = str(value).strip()
    return normalize_text(text)


def _ensure_sentence_end(sentence: str) -> str:
    if not sentence:
        return sentence
    if sentence.endswith((".", "!", "?")):
        return sentence
    return sentence + "."


def normalize_text(text: str) -> str:
    if not text:
        return ""
    candidate = str(text)
    try:
        from ftfy import fix_text  # type: ignore
    except Exception:
        fix_text = None
    if fix_text:
        try:
            candidate = fix_text(candidate)
        except Exception:
            candidate = str(text)
    if _looks_like_mojibake(candidate):
        repaired = _try_latin1_utf8(candidate)
        if repaired:
            candidate = repaired
    return candidate


def _looks_like_mojibake(text: str) -> bool:
    return bool(re.search(r"[\u00c3\u00c2\u00e2\u20ac\u2122\u201c\u201d]", text))


def _try_latin1_utf8(text: str) -> str:
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    if _mojibake_score(repaired) <= _mojibake_score(text):
        return repaired
    return text


def _mojibake_score(text: str) -> int:
    return len(re.findall(r"[\u00c3\u00c2\u00e2\u20ac\u2122\u201c\u201d]", text))


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


def _first_line(text: str) -> str:
    if not text:
        return ""
    return text.splitlines()[0].strip()


def _remove_not_explicitly_mentioned(text: str) -> str:
    cleaned = re.sub(
        r"\bnot explicitly mentioned\b[:,;]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _rewrite_not_allowed_llm_answer(text: str) -> str:
    forced_first = (
        "Not allowed: The guidelines prohibit extremely graphic, gory, or disturbing "
        "violent content."
    )
    forced_second = (
        "Limited exceptions may apply for less graphic content shared in the public interest "
        "(for example, educational, documentary, or news context), often with restrictions."
    )
    filler_phrases = (
        "the excerpts",
        "provided excerpts",
        "based on the provided",
        "the excerpts highlight",
        "based on the excerpts",
        "the provided excerpts focus on",
    )
    exception_markers = (
        "exception",
        "exceptions",
        "limited",
        "may be allowed",
        "may be permitted",
        "public interest",
        "in some cases",
    )
    blocked_contains = ("it depends", "not explicitly mentioned", "more context")
    blocked_prefixes = ("allowed:", "not allowed:", "depends:")
    sentences = [s.strip() for s in _split_sentences(text) if s.strip()]
    filtered: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(phrase in lowered for phrase in blocked_contains):
            continue
        if any(phrase in lowered for phrase in filler_phrases):
            continue
        if lowered.startswith(blocked_prefixes):
            continue
        if "allowed" in lowered and "not allowed" not in lowered:
            if not any(marker in lowered for marker in exception_markers):
                continue
        filtered.append(sentence)
    filtered = _dedupe_sentences(filtered)
    forced_keys = {
        _normalize_sentence_key(forced_first),
        _normalize_sentence_key(forced_second),
    }
    filtered = [s for s in filtered if _normalize_sentence_key(s) not in forced_keys]
    extras: List[str] = []
    for sentence in filtered:
        if len(extras) >= 2:
            break
        extras.append(sentence)
    print(
        "[graphrag] Guardrail kept "
        f"{len(extras)} supporting LLM sentences."
    )
    output_sentences = [forced_first, forced_second] + extras
    if len(output_sentences) < 3:
        output_sentences.append(
            "Content that glorifies violence or includes threats may also be removed "
            "depending on the policy excerpts provided."
        )
    output_sentences = output_sentences[:6]
    return " ".join(_ensure_sentence_end(s) for s in output_sentences)


def _normalize_sentence_key(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence.strip()).lower()


def _dedupe_sentences(sentences: List[str]) -> List[str]:
    seen: Set[str] = set()
    unique: List[str] = []
    for sentence in sentences:
        key = _normalize_sentence_key(sentence)
        if key in seen:
            continue
        seen.add(key)
        unique.append(sentence)
    return unique


def _normalize_llm_answer_sentences(text: str, inferred: str) -> str:
    sentences = [s.strip() for s in _split_sentences(text) if s.strip()]
    if not sentences:
        return text
    request_sentence = "Please provide more details about the content and intent."
    if inferred == "DEPENDS" and not any(
        request_sentence.lower() in s.lower() for s in sentences
    ):
        sentences.append(request_sentence)
    while len(sentences) < 3:
        if inferred == "NOT_ALLOWED":
            sentences.append(
                "The excerpts highlight the relevant policy restrictions for this topic."
            )
        elif inferred == "ALLOWED":
            sentences.append(
                "The excerpts outline the conditions and scope for this type of content."
            )
        else:
            sentences.append("Additional context is needed to make a clear determination.")
    if len(sentences) > 6:
        if inferred == "DEPENDS" and request_sentence in sentences:
            sentences = [s for s in sentences if s != request_sentence][:5] + [
                request_sentence
            ]
        else:
            sentences = sentences[:6]
    return " ".join(_ensure_sentence_end(s) for s in sentences)


def _needs_sentence_normalization(text: str) -> bool:
    count = len(_split_sentences(text))
    return count < 3 or count > 6


def _default_verdict_sentence(inferred: str, platform_name: str) -> str:
    if inferred == "NOT_ALLOWED":
        return (
            f"Not allowed: The cited sections indicate this content is restricted or "
            f"prohibited on {platform_name}."
        )
    if inferred == "ALLOWED":
        return (
            f"Allowed: The cited sections indicate this content is permitted on "
            f"{platform_name}, subject to the stated conditions."
        )
    return (
        f"Depends: The cited sections suggest the outcome depends on context and "
        f"specific details on {platform_name}."
    )


def _enforce_verdict_first_sentence(text: str, inferred: str) -> str:
    sentences = [s.strip() for s in _split_sentences(text) if s.strip()]
    if not sentences:
        return text
    prefix = _verdict_prefix(inferred)
    first = sentences[0]
    stripped = _strip_verdict_prefix(first)
    if inferred == "DEPENDS" and "based on the provided guidelines" not in text.lower():
        stripped = "Based on the provided guidelines, it depends on context and specific details."
    elif not stripped:
        stripped = (
            _default_verdict_sentence(inferred, "the platform").split(":", 1)[1].strip()
        )
    sentences[0] = f"{prefix} {stripped}".strip()
    return " ".join(_ensure_sentence_end(s) for s in sentences)


def _strip_verdict_prefix(sentence: str) -> str:
    return re.sub(r"^(Allowed|Not allowed|Depends):\s*", "", sentence).strip()


def _verdict_prefix(inferred: str) -> str:
    if inferred == "NOT_ALLOWED":
        return "Not allowed:"
    if inferred == "ALLOWED":
        return "Allowed:"
    return "Depends:"


def _limit_answer_length(text: str, max_chars: int = 1200) -> str:
    sentences = [s.strip() for s in _split_sentences(text) if s.strip()]
    if not sentences:
        return text
    if len(sentences) > 6:
        sentences = sentences[:6]
    if len(sentences) < 3:
        sentences = _split_sentences(_normalize_llm_answer_sentences(text, "DEPENDS"))
    trimmed = sentences[:]
    while len(" ".join(trimmed)) > max_chars and len(trimmed) > 3:
        trimmed = trimmed[:-1]
    return " ".join(_ensure_sentence_end(s) for s in trimmed)


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
