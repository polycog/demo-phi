"""
Scoring against the gold labels, occurrence by occurrence.

A gold span's system action is the most protective action among the system's decisions
that overlap it (ESCALATE > REDACT > GENERALIZE > KEEP); no overlapping decision = KEEP.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .domain import Action, Decision

_STRENGTH = {Action.KEEP: 0, Action.GENERALIZE: 1, Action.REDACT: 2, Action.ESCALATE: 3}


@dataclass
class GoldHit:
    doc: str
    text: str
    start: int
    end: int
    expected: Action
    got: Action
    replacement_expected: str | None
    replacement_got: str | None
    trap: str | None
    why: str

    @property
    def outcome(self) -> str:
        if self.got is self.expected:
            if self.expected is Action.GENERALIZE and self.replacement_expected and (
                (self.replacement_got or "").strip() != self.replacement_expected
            ):
                return "wrong-replacement"
            return "correct"
        if self.got is Action.KEEP:
            return "leak"  # PHI left in the released text
        if self.expected is Action.KEEP:
            return "over-redaction"
        if self.got is Action.ESCALATE:
            return "unneeded-review"
        if self.expected is Action.ESCALATE:
            return "missed-review"
        return "wrong-treatment"


def load_gold(path: Path, docs: dict[str, str]) -> list[tuple[str, int, int, dict]]:
    gold = json.loads(path.read_text())
    out = []
    for doc, items in gold.items():
        if doc.startswith("_") or doc not in docs:
            continue
        for g in items:
            pat = re.compile(r"(?<![\w-])" + re.escape(g["text"]) + r"(?![\w]|-\w)")
            for m in pat.finditer(docs[doc]):
                out.append((doc, m.start(), m.end(), g))
    return out


def score(decisions: list[Decision], gold: list[tuple[str, int, int, dict]]) -> tuple[list[GoldHit], list[Decision]]:
    hits, covered = [], set()
    for doc, a, b, g in gold:
        over = [d for d in decisions if d.doc == doc and d.start < b and a < d.end]
        covered.update(id(d) for d in over)
        best = max(over, key=lambda d: _STRENGTH[d.action], default=None)
        hits.append(
            GoldHit(
                doc=doc, text=g["text"], start=a, end=b, expected=Action(g["action"]),
                got=best.action if best else Action.KEEP, replacement_expected=g.get("replacement"),
                replacement_got=best.replacement if best else None, trap=g.get("trap"), why=g["why"],
            )
        )  # fmt: skip
    extras = [d for d in decisions if id(d) not in covered and d.action is not Action.KEEP]
    return hits, extras


def summarize(hits: list[GoldHit], extras: list[Decision]) -> dict[str, int]:
    out: dict[str, int] = {"gold spans": len(hits)}
    for h in hits:
        out[h.outcome] = out.get(h.outcome, 0) + 1
    out["redactions outside gold"] = len(extras)
    return out
