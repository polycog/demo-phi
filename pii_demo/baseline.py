"""
Baseline: the same LLM, asked to do the whole job in one prompt per document.

To keep the comparison about *process* rather than *knowledge*, the prompt carries the
same rulebook the cognition pipeline uses: the Safe Harbor identifiers, the age-90 and
date rules, the re-identification-code rule and the restricted ZIP3 list.
"""

import re
import time

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from .domain import Action, Decision
from .reference import RESTRICTED_ZIP3

PROMPT = """You are an expert HIPAA privacy officer de-identifying clinical-trial documents under the
Safe Harbor method (45 CFR §164.514(b)(2)). The current year is {ref_year}.

Safe Harbor removes these identifiers of the individual or of relatives, employers or household
members of the individual (not of study or care staff):
(A) names; (B) geographic subdivisions smaller than a state (street, city, town, county, ZIP), except
the first 3 digits of a ZIP when that 3-digit area has more than 20,000 people; 3-digit areas with
20,000 or fewer people must become 000. Restricted ZIP3 prefixes: {zip3}.
(C) all elements of dates (except year) directly related to an individual (birth, admission, discharge,
death, enrollment, sample collection ...); all ages over 89 and all elements of dates (including year)
indicative of such age, which may be aggregated as "90+". Dates about documents, protocols, sites,
shipments or reagents are not about an individual.
(D) phone (E) fax (F) email (G) SSN (H) medical record numbers (I) health plan numbers (J) account
numbers (K) certificate/license numbers (L) vehicle ids (M) device ids (N) URLs (O) IP addresses
(P) biometrics (Q) photos (R) any other unique identifying number, characteristic or code.
§164.514(c): a re-identification code assigned by the study is allowed only if it is not derived from
information about the individual (e.g. not built from initials, birth date or record number).
If you know of a residual risk of re-identification, escalate it for human review.

For the document below, list every span you considered, each with one action:
KEEP, GENERALIZE (give the replacement, e.g. "2026", "049**", "90+"), REDACT, or ESCALATE
(withhold pending human review). Copy each span exactly as it appears.

== Document ==
{document}
"""


class BaselineFinding(BaseModel):
    text: str = Field(description="the span, copied exactly from the document")
    action: Action
    replacement: str | None = Field(default=None, description="replacement text for GENERALIZE")
    reason: str = Field(description="one short sentence")


class BaselineReport(BaseModel):
    findings: list[BaselineFinding]


def run_baseline(docs: dict[str, str], llm: Model, *, ref_year: int, timeout: int, say=print) -> tuple[list[Decision], dict[str, float]]:
    agent = Agent(llm, output_type=BaselineReport, model_settings={"timeout": timeout})
    decisions, timings = [], {}
    for name, text in docs.items():
        t0 = time.perf_counter()
        prompt = PROMPT.format(ref_year=ref_year, zip3=", ".join(sorted(RESTRICTED_ZIP3)), document=text)
        report = agent.run_sync(prompt).output
        for f in report.findings:
            pat = re.compile(r"(?<![\w-])" + re.escape(f.text.strip()) + r"(?![\w]|-\w)")
            for m in pat.finditer(text):
                decisions.append(
                    Decision(
                        doc=name, text=m.group(0), start=m.start(), end=m.end(), action=f.action,
                        replacement=f.replacement if f.action is Action.GENERALIZE else
                        ("[REVIEW]" if f.action is Action.ESCALATE else "[REDACTED]" if f.action is Action.REDACT else None),
                        rule="baseline-llm", citation="(model's own reading)", rationale=f.reason,
                    )
                )  # fmt: skip
        timings[name] = time.perf_counter() - t0
        say(f"[baseline] {name}: {len(report.findings)} findings ({timings[name]:.1f}s)")
    return decisions, timings
