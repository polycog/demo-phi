"""
Sub-DP: apply HIPAA Safe Harbor to one investigated mention.

Each rule is an operator: `applies` says whether the rule is *allowed* to decide this
mention; it never asks whether it is the *best* rule. General rules ("names are
removed") and their exceptions ("staff names are out of scope") are both proposed, and
a policy evaluator picks among them. Swapping the evaluator changes the policy without
touching a single rule.
"""

from dataclasses import dataclass, field
from typing import ClassVar, cast

from cognition import DecisionProcess, IOContainer, NamedObject, Operator, sorting_evaluator

from ..domain import Action, CodeKind, DateRole, Decision, GeoLevel, Mention, MentionKind, Subject, Whose
from ..reference import AGE, RESTRICTED_ZIP3, SAFE_HARBOR, birth_year, digits, initials, year_only

K = MentionKind

LABEL = {
    K.PERSON_NAME: "NAME",
    K.ORGANIZATION: "ORGANIZATION",
    K.GEOGRAPHIC: "LOCATION",
    K.DATE: "DATE",
    K.AGE: "AGE",
    K.CONTACT: "CONTACT",
    K.ID_CODE: "ID",
    K.UNIQUE_CHARACTERISTIC: "REVIEW",
    K.BIOMEDICAL_TERM: "TERM",
}

IDENTIFIES_INDIVIDUAL = {Whose.SUBJECT.value, Whose.FAMILY_OR_HOUSEHOLD.value, Whose.EMPLOYER.value}


@dataclass
class Assessment:
    mention: Mention
    subjects: dict[str, Subject] = field(default_factory=dict)
    decision: Decision | None = None
    considered: list[str] = field(default_factory=list)  # trace: rules that competed (and their order)


type Verdict = tuple[str | None, str, list[str]]  # replacement, rationale, evidence


class Rule(Operator[Assessment]):
    """A Safe Harbor rule. Subclasses set the class attributes and implement applies/verdict."""

    action: ClassVar[Action]
    citation: ClassVar[str]
    specificity: ClassVar[int]  # smaller = more specific exception
    role: ClassVar[str] = "rule"  # "guard" | "rule" | "fallback"

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        raise NotImplementedError

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        raise NotImplementedError

    def can_perform(self, state: Assessment, io: IOContainer) -> bool:
        return state.decision is None and self.applies(state.mention, state, io)

    def perform(self, state: Assessment, io: IOContainer) -> None:
        m = state.mention
        replacement, rationale, evidence = self.verdict(m, state, io)
        if replacement is None and self.action is Action.REDACT:
            replacement = f"[{LABEL[m.kind]}]"
        if self.action is Action.ESCALATE:
            replacement = "[REVIEW]"
        state.decision = Decision(
            doc=m.doc,
            text=m.text,
            start=m.start,
            end=m.end,
            action=self.action,
            replacement=replacement,
            rule=self.name,
            citation=SAFE_HARBOR[self.citation],
            rationale=rationale,
            evidence=_answer_evidence(m) + evidence,
        )


def _answer_evidence(m: Mention) -> list[str]:
    out = [f"proposed by {m.proposed_by} as {m.kind.value}"]
    for q, a in m.answers.items():
        if q.endswith("_by"):
            continue
        by = m.answers.get(f"{q}_by", "llm")
        conf = m.confidence.get(q, 0.0)
        out.append(f"{q} = {a} ({by}, agreement {conf:.0%})" if by == "llm" else f"{q} = {a} ({by})")
    return out


def _ans(m: Mention, q: str) -> str | None:
    return m.answers.get(q)


def _age(m: Mention) -> int | None:
    found = AGE.search(m.text)
    return int(found.group(1)) if found else None


def _is_year_only(text: str) -> bool:
    return text.strip().isdigit() and len(text.strip()) == 4


# --- guards ---------------------------------------------------------------------------


class LowConfidence(Rule):
    """Any question the decision depends on was answered with too little agreement, or not at all"""

    action, citation, specificity, role = Action.ESCALATE, "ii", 0, "guard"

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return any(a == "none" for a in m.answers.values()) or any(
            c < float(io.a.min_confidence) for c in m.confidence.values()
        )

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        weak = [q for q, c in m.confidence.items() if c < float(io.a.min_confidence) or m.answers[q] == "none"]
        return None, f"the LLM's answers to {', '.join(weak)} were not consistent enough to act on", []


class UniqueCharacteristic(Rule):
    """A distinctive personal fact: not enumerated, so Safe Harbor needs a human to judge it"""

    action, citation, specificity, role = Action.ESCALATE, "R", 0, "guard"

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.UNIQUE_CHARACTERISTIC

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        ev = []
        subj = s.subjects.get(m.subject_code or "")
        age, year = _age_and_year_in(m.text)
        if age is not None and year is not None:
            born = year - age
            ev.append(f"'{m.text}' implies birth year ≈{born}, i.e. age {int(io.a.ref_year) - born} in {io.a.ref_year}")
        if subj and subj.birth_dates:
            ev.append(f"{subj.name} birth date on file: {subj.birth_dates[0]} (from {subj.source_of(subj.birth_dates[0])})")
        return None, "a unique identifying characteristic (R); hold for privacy review", ev


def _age_and_year_in(text: str) -> tuple[int | None, int | None]:
    import re

    a = re.search(r"\bage (\d{1,3})\b", text)
    y = birth_year(text)
    return (int(a.group(1)) if a else None), y


# --- identifiers and codes --------------------------------------------------------------


class DerivedCode(Rule):
    """A code built from the subject's own identifiers is not a permitted re-identification code"""

    action, citation, specificity = Action.REDACT, "c", 1

    def _hits(self, m: Mention, s: Assessment) -> list[str]:
        code_digits, hits = digits(m.text), []
        letters = "".join(ch for ch in m.text if ch.isalpha()).upper()
        for subj in s.subjects.values():
            for mrn in subj.record_numbers:
                d = digits(mrn)
                if len(d) >= 5 and d in code_digits and d != code_digits:
                    hits.append(f"contains MRN {mrn} of {subj.name} (learned from {subj.source_of(mrn)})")
            for dob in subj.birth_dates:
                d = digits(dob)
                if len(d) >= 8 and d in code_digits:
                    hits.append(f"contains birth date {dob} of {subj.name} (learned from {subj.source_of(dob)})")
            for name in subj.names:
                ini = initials(name)
                if hits and len(ini) >= 2 and letters.startswith(ini):
                    hits.append(f"starts with initials {ini} of {name} (learned from {subj.source_of(name)})")
        return hits

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.ID_CODE and _ans(m, "code_kind") != CodeKind.MEDICAL_RECORD_NUMBER.value and bool(
            self._hits(m, s)
        )

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "the code is derived from the individual's identifiers, so it is itself an identifier", self._hits(
            m, s
        )


class RecordNumber(Rule):
    action, citation, specificity = Action.REDACT, "H", 3

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.ID_CODE and _ans(m, "code_kind") == CodeKind.MEDICAL_RECORD_NUMBER.value

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "medical record number", []


class AccountNumber(Rule):
    action, citation, specificity = Action.REDACT, "I/J", 3

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.ID_CODE and _ans(m, "code_kind") == CodeKind.ACCOUNT_OR_PLAN_NUMBER.value

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "health plan or account number", []


class StudyCode(Rule):
    """Trial-assigned subject and sample codes are permitted re-identification codes"""

    action, citation, specificity = Action.KEEP, "c", 4

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.ID_CODE and _ans(m, "code_kind") in (
            CodeKind.STUDY_SUBJECT_CODE.value,
            CodeKind.SAMPLE_CODE.value,
        )

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "study-assigned code; permitted as long as it is not derived from identifiers", [
            "no identifier of any known subject found inside the code"
        ]


class AdministrativeCode(Rule):
    action, citation, specificity = Action.KEEP, "none", 5

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.ID_CODE and _ans(m, "code_kind") == CodeKind.ADMINISTRATIVE.value

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "identifies a protocol, lot or document, not a person", []


# --- ages and dates -----------------------------------------------------------------------


class AgeOver89(Rule):
    action, citation, specificity = Action.GENERALIZE, "C", 2

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.AGE and (_age(m) or 0) > 89

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return "90+", f"age {_age(m)} is over 89 and must be aggregated", []


class AgeAllowed(Rule):
    action, citation, specificity = Action.KEEP, "C", 5

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.AGE and _age(m) is not None and _age(m) <= 89  # type: ignore[operator]

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, f"age {_age(m)} is 89 or under", []


class BirthDateOver89(Rule):
    """Even the year of birth must go when it shows the person is over 89"""

    action, citation, specificity = Action.REDACT, "C", 2

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        y = birth_year(m.text)
        return m.kind is K.DATE and _ans(m, "date_role") == DateRole.BIRTH.value and y is not None and (
            int(io.a.ref_year) - y > 89
        )

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        y = birth_year(m.text)
        return "[DOB: age 90+]", "the birth year shows an age over 89, so the year must go too", [
            f"born {y}: age {int(io.a.ref_year) - (y or 0)} in {io.a.ref_year}"
        ]


class PersonalDate(Rule):
    action, citation, specificity = Action.GENERALIZE, "C", 4

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return (
            m.kind is K.DATE
            and _ans(m, "date_role") in (DateRole.BIRTH.value, DateRole.PERSONAL_EVENT.value)
            and not _is_year_only(m.text)
            and year_only(m.text) is not None
        )

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return year_only(m.text), f"a {_ans(m, 'date_role')} date of an individual: only the year may remain", []


class YearAllowed(Rule):
    action, citation, specificity = Action.KEEP, "C", 4

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.DATE and _is_year_only(m.text) and _ans(m, "date_role") != DateRole.ADMINISTRATIVE.value

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        y = birth_year(m.text) or 0
        ev = [f"born {y}: age {int(io.a.ref_year) - y} in {io.a.ref_year}"] if _ans(m, "date_role") == "birth" else []
        return None, "a year on its own is allowed", ev


class AdministrativeDate(Rule):
    action, citation, specificity = Action.KEEP, "none", 5

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.DATE and _ans(m, "date_role") == DateRole.ADMINISTRATIVE.value

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "the date is about a document, site, shipment or reagent, not an individual", []


# --- places -------------------------------------------------------------------------------------


class RestrictedZip(Rule):
    action, citation, specificity = Action.GENERALIZE, "B", 2

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return _ans(m, "geo_level") == GeoLevel.ZIP.value and digits(m.text)[:3] in RESTRICTED_ZIP3

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return "000**", "ZIP3 area has 20,000 people or fewer, so it must be 000", [
            f"{digits(m.text)[:3]} is on the HHS restricted ZIP3 list"
        ]


class Zip3(Rule):
    action, citation, specificity = Action.GENERALIZE, "B", 3

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return _ans(m, "geo_level") == GeoLevel.ZIP.value and digits(m.text)[:3] not in RESTRICTED_ZIP3

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return f"{digits(m.text)[:3]}**", "only the first three ZIP digits may remain", [
            f"{digits(m.text)[:3]} is not on the HHS restricted ZIP3 list"
        ]


class SubStatePlace(Rule):
    action, citation, specificity = Action.REDACT, "B", 3

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return _ans(m, "geo_level") in (GeoLevel.STREET_ADDRESS.value, GeoLevel.TOWN_OR_CITY.value, GeoLevel.COUNTY.value)

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, f"a {_ans(m, 'geo_level')} is smaller than a state", []


class StateOrCountry(Rule):
    action, citation, specificity = Action.KEEP, "B", 5

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return _ans(m, "geo_level") in (GeoLevel.STATE.value, GeoLevel.COUNTRY.value)

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "states and countries are allowed", []


# --- people, organizations, contacts -----------------------------------------------------------


class NotAPerson(Rule):
    action, citation, specificity = Action.KEEP, "none", 3

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return _ans(m, "whose") == Whose.NOT_A_PERSON.value

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "names no one (eponym, gene, cell line, product ...)", []


class StaffOutOfScope(Rule):
    """Safe Harbor covers the individual, relatives, employers and household members, not staff"""

    action, citation, specificity = Action.KEEP, "scope", 3

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return _ans(m, "whose") == Whose.STAFF.value

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "belongs to study or care staff, which Safe Harbor does not require removing", []


class IdentifierOfIndividual(Rule):
    action, citation, specificity = Action.REDACT, "A", 6

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind in (K.PERSON_NAME, K.ORGANIZATION) and _ans(m, "whose") in IDENTIFIES_INDIVIDUAL

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, f"names the {_ans(m, 'whose')}".replace("_", " "), []


class Contact(Rule):
    action, citation, specificity = Action.REDACT, "D", 6

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.CONTACT and _ans(m, "whose") != Whose.NOT_A_PERSON.value

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "phone, fax, email, URL or IP address", []


class AnyPersonName(Rule):
    """The general rule that exceptions override: a human name is removed"""

    action, citation, specificity = Action.REDACT, "A", 8

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.PERSON_NAME and _ans(m, "whose") != Whose.NOT_A_PERSON.value

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "a person's name", []


class BiomedicalTerm(Rule):
    action, citation, specificity = Action.KEEP, "none", 5

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return m.kind is K.BIOMEDICAL_TERM and _ans(m, "whose") not in IDENTIFIES_INDIVIDUAL

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "a scientific term", []


class NoRuleApplies(Rule):
    action, citation, specificity, role = Action.ESCALATE, "ii", 99, "fallback"

    def applies(self, m: Mention, s: Assessment, io: IOContainer) -> bool:
        return True

    def verdict(self, m: Mention, s: Assessment, io: IOContainer) -> Verdict:
        return None, "no Safe Harbor rule covers this span; a human should look", []


RULES: list[type[Rule]] = [
    LowConfidence, UniqueCharacteristic, DerivedCode, RecordNumber, AccountNumber, StudyCode,
    AdministrativeCode, AgeOver89, AgeAllowed, BirthDateOver89, PersonalDate, YearAllowed,
    AdministrativeDate, RestrictedZip, Zip3, SubStatePlace, StateOrCountry, NotAPerson,
    StaffOutOfScope, IdentifierOfIndividual, Contact, AnyPersonName, BiomedicalTerm, NoRuleApplies,
]  # fmt: skip


# --- policies: how competing valid rules are ranked ---------------------------------------------

_PROTECTIVE = {Action.REDACT: 0, Action.GENERALIZE: 1, Action.KEEP: 2, Action.ESCALATE: 3}
_ROLE = {"guard": 0, "rule": 1, "fallback": 2}


def _rule(a: object) -> Rule:
    return cast(Rule, cast(NamedObject, a).params["_op"])


POLICIES = {
    # Safe Harbor as written: guards first, then the most specific exception wins
    "safe-harbor": sorting_evaluator(lambda a, s, io: POLICIES_KEYS["safe-harbor"](a), name="most_specific_rule"),
    # organizational policy: guards first, then the most protective valid rule wins
    "conservative": sorting_evaluator(lambda a, s, io: POLICIES_KEYS["conservative"](a), name="most_protective_rule"),
}


def build(policy: str) -> DecisionProcess[Assessment]:
    dp = DecisionProcess[Assessment](lambda: Assessment(mention=None))  # type: ignore[arg-type]
    for r in RULES:
        dp.add_operator(r(_snake(r.__name__), terminal=True))
    dp.add_action_evaluator(POLICIES[policy])
    dp.add_action_evaluator(_trace)
    return dp


def _trace(s: Assessment, io: IOContainer, actions: object) -> list:
    """Ranks nothing; records which rules were valid, in policy order, for the explanation"""
    key = POLICIES_KEYS[io.a.policy]
    s.considered = [f"{_rule(a).name} -> {_rule(a).action.value}" for a in sorted(actions, key=lambda a: key(a))]  # type: ignore[arg-type]
    return []


POLICIES_KEYS = {
    "safe-harbor": lambda a: (_ROLE[_rule(a).role], _rule(a).specificity),
    "conservative": lambda a: (_ROLE[_rule(a).role], _PROTECTIVE[_rule(a).action], _rule(a).specificity),
}


def _snake(n: str) -> str:
    return "".join(f"_{c.lower()}" if c.isupper() else c for c in n).lstrip("_")


def decide(
    dp: DecisionProcess[Assessment], m: Mention, subjects: dict[str, Subject], policy: str, **args: object
) -> tuple[Decision, list[str]]:
    """Wrapper: run the rules sub-DP for one mention. Returns the decision and the rules that competed."""
    dp.reinit()
    dp.state.mention, dp.state.subjects = m, subjects
    dp(suppress_errors=False, policy=policy, **args)
    final = dp.state
    assert final.decision is not None, f"no decision for {m.name}"
    return final.decision, final.considered or [f"{final.decision.rule} -> {final.decision.action.value}"]
