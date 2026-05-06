"""Same-site sitemap filtering, scoped URL lists, and HTML internal-link injection."""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

# Common English stopwords + web noise (keep path tokens even if short elsewhere)
_STOP = frozenset(
    """
    that this with from have your will been were said each which their time would
    there could other than first into more very what when where about after also
    back before being between both but can come day did does even just only over
    some take them then these they want well work year site page home http https
    www com au org net one two may its our out any all new old get see how way who
    now use her she him his she they them most much such same each both few many
    """.split()
)

# Tokens that appear in almost every agency URL — ignore for relevance matching
_GENERIC_URL = frozenset(
    """
    development services company digital marketing integration solutions business
    website web online agency australia design studio consulting software technology
    tech blog professional experts team contact about home services item model sku
    variant pm floor
    """.split()
)


def _norm_host(url: str) -> str:
    try:
        h = urlparse(url).netloc.lower()
        if h.startswith("www."):
            return h[4:]
        return h
    except Exception:
        return ""


def filter_same_site(user_urls: list[str], candidate_urls: list[str]) -> list[str]:
    """Keep sitemap URLs whose host matches any user-provided page URL."""
    hosts = {_norm_host(u) for u in user_urls if u and u.strip()}
    if not hosts:
        return list(dict.fromkeys(candidate_urls))[:60]

    out = []
    seen = set()
    for u in candidate_urls:
        if not u or not str(u).strip():
            continue
        u = str(u).strip()
        if u in seen:
            continue
        if _norm_host(u) in hosts:
            out.append(u)
            seen.add(u)
    if out:
        return out
    logger.warning(
        "No sitemap URLs matched user page host(s) %s — using first sitemap URLs as fallback",
        hosts,
    )
    return list(dict.fromkeys(candidate_urls))[:60]


def _path_segments(url: str) -> list[str]:
    try:
        p = urlparse(url).path.strip("/")
        return [x for x in p.split("/") if x]
    except Exception:
        return []


def _keywords_from_url_path(url: str) -> set[str]:
    out: set[str] = set()
    for seg in _path_segments(url):
        for part in re.split(r"[\-_]+", seg.lower()):
            if len(part) > 3:
                out.add(part)
    return out


def _keywords_from_page_text(text: str, max_chars: int = 8000) -> set[str]:
    t = (text or "").lower()[:max_chars]
    words = re.findall(r"[a-z]{4,}", t)
    return {w for w in words if w not in _STOP and w not in _GENERIC_URL}


def _sig_path_tokens(url: str) -> set[str]:
    return _keywords_from_url_path(url) - _GENERIC_URL


def _segment_topic_overlap(user_urls: list[str], cand_url: str) -> bool:
    """True if first path segments share a non-generic token (mobile vs mobile-app...)."""
    cu = _path_segments(cand_url)
    if not cu:
        return False
    cand_words = set(re.findall(r"[a-z]{3,}", cu[0].lower())) - _GENERIC_URL
    for u in user_urls:
        su = _path_segments(u)
        if not su:
            continue
        user_words = set(re.findall(r"[a-z]{3,}", su[0].lower())) - _GENERIC_URL
        if cand_words & user_words:
            return True
    return False


def filter_urls_by_page_relevance(
    user_urls: list[str],
    candidate_urls: list[str],
    page_text: str,
    *,
    max_urls: int = 28,
) -> list[str]:
    """
    Narrow sitemap URLs to those aligned with the user-selected page(s).
    Prevents unrelated site sections (e.g. Salesforce, real estate) from steering the model.
    """
    if not candidate_urls:
        return []

    focus: set[str] = set()
    for u in user_urls:
        if u:
            focus |= _sig_path_tokens(u)
    focus |= _keywords_from_page_text(page_text)

    user_prefixes: list[tuple[str, ...]] = []
    for u in user_urls:
        segs = _path_segments(u)
        if segs:
            user_prefixes.append(tuple(segs[: min(4, len(segs))]))

    scored: list[tuple[int, str]] = []
    for u in candidate_urls:
        if not u or not str(u).strip():
            continue
        u = str(u).strip()
        score = 0
        psegs = _path_segments(u)
        pk_sig = _sig_path_tokens(u)

        topic_overlap = pk_sig & focus
        score += min(len(topic_overlap), 12) * 6

        pt = tuple(psegs[:4]) if psegs else ()
        for up in user_prefixes:
            if not up or not pt:
                continue
            if pt[0] == up[0]:
                score += 22
            if len(up) >= 2 and len(pt) >= 2 and pt[:2] == up[:2]:
                score += 35

        if _segment_topic_overlap(user_urls, u):
            score += 18

        blob = (page_text or "").lower()
        for t in _path_tokens(u):
            if len(t) > 3 and t not in _GENERIC_URL and t in blob:
                score += 3

        scored.append((score, u))

    scored.sort(key=lambda x: (-x[0], x[1]))

    strong = [(s, u) for s, u in scored if s >= 14]
    loose = [(s, u) for s, u in scored if s >= 6]
    positive = [(s, u) for s, u in scored if s > 0]

    if len(strong) >= 4:
        pool_iter = strong
    elif len(loose) >= 4:
        pool_iter = loose
    elif positive:
        pool_iter = positive
    else:
        logger.warning(
            "No sitemap URLs scored against page content — skipping unrelated links in prompts"
        )
        pool_iter = []

    keep: list[str] = []
    seen: set[str] = set()
    for _s, u in pool_iter:
        if u in seen:
            continue
        keep.append(u)
        seen.add(u)
        if len(keep) >= max_urls:
            break

    # User's own URLs first for injection / prompts (always include source pages)
    ordered: list[str] = []
    seen = set()
    for u in user_urls:
        if u:
            u = str(u).strip()
            if u not in seen:
                ordered.append(u)
                seen.add(u)
    for u in keep:
        if u not in seen:
            ordered.append(u)
            seen.add(u)

    return ordered[:max_urls]


def _path_tokens(url: str) -> set[str]:
    try:
        p = urlparse(url)
        path = unquote(p.path or "").lower()
        return {
            t
            for t in re.findall(r"[a-z0-9]{3,}", path.replace("/", " "))
            if len(t) > 2
        }
    except Exception:
        return set()


def _answer_vocab(answer: str, question: str) -> set[str]:
    blob = ((answer or "") + " " + (question or "")).lower()
    words = re.findall(r"[a-z]{4,}", blob)
    return {w for w in words if w not in _STOP and w not in _GENERIC_URL}


def vocab_from_keywords_csv(keywords: str | None) -> set[str]:
    if not keywords or not str(keywords).strip():
        return set()
    out: set[str] = set()
    for part in re.split(r"[,;]+", str(keywords)):
        part = part.strip().lower()
        out.update(w for w in re.findall(r"[a-z]{4,}", part) if w not in _GENERIC_URL)
    return out


def _pick_url_with_token_overlap(
    answer: str,
    question: str,
    pool: list[str],
    *,
    keyword_vocab: set[str] | None = None,
) -> tuple[str | None, set[str]]:
    """
    Pick a URL only if its path shares meaningful token(s) with the answer text.
    Returns (url, intersecting_tokens) or (None, set()).
    """
    kwv = keyword_vocab or set()
    aw = _answer_vocab(answer, question)
    best_u: str | None = None
    best_score = 0
    best_inter: set[str] = set()

    for u in pool:
        pt = _sig_path_tokens(u)
        inter = pt & aw
        if not inter:
            continue
        score = sum(3 + min(len(t), 12) for t in inter)
        score += sum(4 for t in pt & kwv if t)
        if score > best_score:
            best_score = score
            best_u = u
            best_inter = inter

    if best_u is None:
        return None, set()

    if len(best_inter) == 1:
        only = next(iter(best_inter))
        if len(only) < 6:
            return None, set()

    return best_u, best_inter


def _wrap_first_word_match(answer: str, url: str, tokens: set[str]) -> str | None:
    """
    Wrap the first whole-word occurrence of an overlapping token in `answer`.
    Anchor text is exactly the word(s) as written in the answer — no 'read more'.
    """
    if not answer or not tokens:
        return None
    # Prefer multi-word phrase matches from URL slugs (e.g. "face-mask" -> "face mask").
    # This avoids linking just one word when the full phrase exists in the answer.
    segs = _path_segments(url)
    phrase_cands: list[str] = []
    for seg in segs:
        words = [w for w in re.split(r"[\-_]+", seg.lower()) if re.fullmatch(r"[a-z0-9]{2,}", w)]
        if len(words) < 2:
            continue
        # Longest phrase first, then shorter n-grams.
        for n in range(len(words), 1, -1):
            for i in range(0, len(words) - n + 1):
                part = words[i : i + n]
                if not any(w in tokens for w in part):
                    continue
                phrase = " ".join(part)
                if phrase not in phrase_cands:
                    phrase_cands.append(phrase)

    for phrase in phrase_cands:
        pat = re.compile(r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b", re.I)
        m = pat.search(answer)
        if not m:
            continue
        start, end = m.span()
        inner = answer[start:end]
        link = f'<a href="{url}" class="faq-inline-link">{inner}</a>'
        return answer[:start] + link + answer[end:]

    for tok in sorted(tokens, key=len, reverse=True):
        if len(tok) < 4:
            continue
        pat = re.compile(r"\b" + re.escape(tok) + r"\b", re.I)
        m = pat.search(answer)
        if not m:
            continue
        start, end = m.span()
        inner = answer[start:end]
        link = f'<a href="{url}" class="faq-inline-link">{inner}</a>'
        return answer[:start] + link + answer[end:]
    return None


def answer_has_internal_anchor(answer: str, pool: list[str]) -> bool:
    if not answer:
        return False
    if re.search(r"<a\s+[^>]*\bhref\s*=", answer, re.I):
        return True
    low = answer.lower()
    return any(u and u in low for u in pool)


def apply_inline_internal_links(
    faqs: list[dict],
    pool: list[str],
    *,
    keywords_csv: str | None = None,
) -> list[dict]:
    """
    Optionally add one inline <a> when a URL path token matches text already in the answer.
    If no confident overlap exists for an FAQ, that answer is left unchanged (no link).
    When linking, wrap the first matching word only; no trailing CTAs.
    """
    if not faqs or not pool:
        return faqs
    pool = list(dict.fromkeys(u.strip() for u in pool if u and str(u).strip()))
    if not pool:
        return faqs

    kw_vocab = vocab_from_keywords_csv(keywords_csv)

    for faq in faqs:
        if not isinstance(faq, dict):
            continue
        ans = (faq.get("answer") or "").strip()
        q = (faq.get("question") or "").strip()
        if not ans or answer_has_internal_anchor(ans, pool):
            continue

        pick, inter = _pick_url_with_token_overlap(
            ans, q, pool, keyword_vocab=kw_vocab
        )
        if not pick or not inter:
            continue

        updated = _wrap_first_word_match(ans, pick, inter)
        if updated:
            faq["answer"] = updated

    return faqs
