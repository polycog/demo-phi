"""
System 1: propose candidate spans.

The LLM (via `ModelPopulator`) proposes typed spans; a few regular expressions add
cheap proposals for formats that never need judgment. Nothing here decides anything:
every proposal becomes a `Mention` that the decision processes investigate.
"""

import re
from dataclasses import dataclass

from pydantic_ai.models import Model

from cognition import ModelPopulator

from .domain import Extraction, Mention, MentionKind
from .reference import PATTERNS, SUBJECT_CODE

TASK = (
    "You assist a privacy officer reviewing clinical-trial documents. "
    "List every span that could identify, locate, date, contact or describe a person "
    "(including staff and relatives), every identifier or code, and every scientific term that "
    "contains a person's name. Be exhaustive; another process decides what to do with each span."
)

extractor = ModelPopulator(Extraction, TASK)

# a span shown alone is never a sufficient basis for a decision: the LLM sees this much context
_SENTENCE_SPLIT = re.compile(r"(?<=[.;:])\s+(?=[A-Z])")


@dataclass
class _Span:
    start: int
    end: int
    kind: MentionKind
    source: str

    @property
    def length(self) -> int:
        return self.end - self.start


def _occurrences(text: str, needle: str) -> list[tuple[int, int]]:
    """All whole-token occurrences of needle in text"""
    out = []
    if not needle.strip():
        return out
    pat = re.compile(r"(?<![\w-])" + re.escape(needle) + r"(?![\w]|-\w)")
    for m in pat.finditer(text):
        out.append((m.start(), m.end()))
    if not out:  # tolerate case differences from the model
        pat = re.compile(r"(?<![\w-])" + re.escape(needle) + r"(?![\w]|-\w)", re.IGNORECASE)
        out = [(m.start(), m.end()) for m in pat.finditer(text)]
    return out


def _remainders(outer: _Span, inner: _Span, text: str) -> list[_Span]:
    """Pieces of `outer` left after removing `inner`, trimmed of punctuation"""
    pieces = []
    for a, b in ((outer.start, inner.start), (inner.end, outer.end)):
        seg = text[a:b]
        lead = len(seg) - len(seg.lstrip(" ,;:()-"))
        trail = len(seg) - len(seg.rstrip(" ,;:()-"))
        a2, b2 = a + lead, b - trail
        if b2 - a2 >= 2 and re.search(r"\w", text[a2:b2]):
            pieces.append(_Span(a2, b2, outer.kind, outer.source))
    return pieces


# compound kinds are judged as a whole, so the spans inside them are not split out
_COMPOUND = {MentionKind.UNIQUE_CHARACTERISTIC, MentionKind.BIOMEDICAL_TERM}


def _resolve(spans: list[_Span], text: str) -> list[_Span]:
    """Make spans non-overlapping: atomic inner spans win, except inside compound kinds"""
    changed = True
    while changed:
        changed = False
        spans.sort(key=lambda s: (s.start, -s.length))
        for i, a in enumerate(spans):
            for b in spans[i + 1 :]:
                if b.start >= a.end:
                    break
                if (a.start, a.end) == (b.start, b.end):  # same span: prefer the pattern's kind
                    keep, drop = (b, a) if b.source == "pattern" else (a, b)
                    keep.source = "llm+pattern" if a.source != b.source else keep.source
                    spans.remove(drop)
                elif a.start <= b.start and b.end <= a.end:  # a contains b
                    if a.kind in _COMPOUND or a.kind is b.kind:  # "Ruth Marsh" beats "Ruth"
                        spans.remove(b)
                    else:
                        spans.remove(a)
                        spans.extend(_remainders(a, b, text))
                else:  # partial overlap: keep the longer one
                    spans.remove(b if a.length >= b.length else a)
                changed = True
                break
            if changed:
                break
    return sorted(spans, key=lambda s: s.start)


def _context(text: str, start: int, end: int) -> str:
    lines = text.splitlines(keepends=True)
    title = lines[0].strip() if lines else ""
    header = lines[1].strip() if len(lines) > 1 and "," in lines[1] and not re.search(r"\d", lines[1]) else ""
    offset = 0
    for line in lines:
        if offset <= start < offset + len(line):
            sentences, pos, chosen = _SENTENCE_SPLIT.split(line), offset, []
            for k, sent in enumerate(sentences):
                s_start = text.find(sent, pos)
                pos = s_start + len(sent)
                if s_start <= start < pos or (chosen and s_start < end):
                    chosen = sentences[max(0, k - 1) : k + 1]
                    break
            body = " ".join(c.strip() for c in chosen) or line.strip()
            parts = [f"[document: {title}]"] + ([f"[columns: {header}]"] if header else []) + [body]
            return "\n".join(parts)
        offset += len(line)
    return title


def _subject_code(text: str, start: int) -> str | None:
    """The study subject the span is about: nearest preceding code on its line, else in the document"""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    line_end = len(text) if line_end < 0 else line_end
    on_line = [m for m in SUBJECT_CODE.finditer(text, line_start, line_end)]
    before = [m for m in on_line if m.start() <= start] or on_line
    if before:
        return before[-1].group(0)
    earlier = [m for m in SUBJECT_CODE.finditer(text, 0, start)]
    return earlier[-1].group(0) if earlier else None


def pattern_spans(text: str) -> list[_Span]:
    kinds = {"date": MentionKind.DATE, "contact": MentionKind.CONTACT, "geographic": MentionKind.GEOGRAPHIC}
    return [
        _Span(m.start(), m.end(), kinds[k], "pattern") for k, pat in PATTERNS.items() for m in pat.finditer(text)
    ]


def extract(doc: str, text: str, llm: Model, timeout_secs: int) -> tuple[list[Mention], list[str]]:
    """Proposals for one document, plus notes on LLM proposals that could not be located"""
    proposals = extractor(text, llm, timeout_secs=timeout_secs).mentions
    spans, notes, seen = pattern_spans(text), [], set()
    for p in proposals:
        if (p.text, p.kind) in seen:
            continue
        seen.add((p.text, p.kind))
        occ = _occurrences(text, p.text.strip())
        if not occ:
            notes.append(f"LLM proposed {p.text!r} ({p.kind.value}) but it is not in the text")
        spans.extend(_Span(a, b, p.kind, "llm") for a, b in occ)

    mentions = []
    for n, s in enumerate(_resolve(spans, text), 1):
        mentions.append(
            Mention(
                name=f"{doc}#{n}",
                doc=doc,
                text=text[s.start : s.end],
                kind=s.kind,
                start=s.start,
                end=s.end,
                context=_context(text, s.start, s.end),
                proposed_by=s.source,
                subject_code=_subject_code(text, s.start),
            )
        )
    return mentions, notes
