"""
Sub-DP: decide which narrow questions to ask about one mention, and ask them.

Deterministic code chooses the questions; the LLM only answers them, as typed enum
values, with agreement across several trials as its confidence. Questions that a
pattern can settle are proposed too, and an evaluator prefers them over the LLM.
"""

from dataclasses import dataclass
from enum import Enum
from typing import cast

from cognition import (
    DecisionProcess,
    EnumClassifier,
    IOContainer,
    NamedObject,
    Operator,
    create_elaborator,
    sorting_evaluator,
)

from ..domain import CodeKind, DateRole, GeoLevel, Mention, MentionKind, Whose
from ..reference import SUBJECT_CODE, US_STATES, ZIP5

K = MentionKind

# question -> (answer type, kinds of mention it is asked about, prompt task)
QUESTIONS: dict[str, tuple[type[Enum], set[MentionKind], str]] = {
    "whose": (
        Whose,
        {K.PERSON_NAME, K.ORGANIZATION, K.CONTACT, K.BIOMEDICAL_TERM},
        "Clinical-trial privacy review. Given the context, who does the quoted phrase identify "
        "or belong to?",
    ),
    "date_role": (
        DateRole,
        {K.DATE},
        "Clinical-trial privacy review. Given the context, what is the quoted date the date of?",
    ),
    "code_kind": (
        CodeKind,
        {K.ID_CODE},
        "Clinical-trial privacy review. Given the context, what does the quoted identifier label?",
    ),
    "geo_level": (
        GeoLevel,
        {K.GEOGRAPHIC},
        "Clinical-trial privacy review. Given the context, what kind of place is the quoted phrase?",
    ),
}

CLASSIFIERS = {q: EnumClassifier(t, task) for q, (t, _, task) in QUESTIONS.items()}


def utterance(m: Mention) -> str:
    return f'{m.context}\n\nQuoted phrase: "{m.text}"'


@dataclass
class Investigation:
    mention: Mention


dp = DecisionProcess(lambda: Investigation(mention=None))  # type: ignore[arg-type]

dp.add_elaborator(
    create_elaborator(
        "open_questions",
        open=lambda s, io: [
            q for q, (_, kinds, _) in QUESTIONS.items() if s.mention.kind in kinds and q not in s.mention.answers
        ],
    )
)
dp.add_termination_check(lambda s, io: not io.e.open)


class Ask(Operator[Investigation]):
    """Ask the LLM one typed question (expensive: done once, in perform)"""

    def can_perform(self, state: Investigation, io: IOContainer) -> bool:
        return self.params["question"] in io.e.open

    def perform(self, state: Investigation, io: IOContainer) -> None:
        q = self.params["question"]
        m = state.mention
        answer, conf = CLASSIFIERS[q](utterance(m), io.a.llm, num_trials=int(io.a.trials), timeout_secs=int(io.a.timeout))
        m.answers[q] = answer.value if answer is not None else "none"
        m.confidence[q] = float(conf)


class Settle(Operator[Investigation]):
    """Answer a question from the text's format alone (cheap, certain)"""

    def can_perform(self, state: Investigation, io: IOContainer) -> bool:
        return self.params["question"] in io.e.open and self.params["test"](state.mention.text.strip()) is not None

    def perform(self, state: Investigation, io: IOContainer) -> None:
        q = self.params["question"]
        state.mention.answers[q] = self.params["test"](state.mention.text.strip())
        state.mention.confidence[q] = 1.0
        state.mention.answers[f"{q}_by"] = "pattern"


for q in QUESTIONS:
    dp.add_operator(Ask(f"ask_{q}", question=q, cost=10))


def _geo(t: str) -> str | None:
    if ZIP5.match(t):
        return GeoLevel.ZIP.value
    if t in US_STATES or t.lower() in US_STATES:
        return GeoLevel.STATE.value
    return None


def _code(t: str) -> str | None:
    return CodeKind.STUDY_SUBJECT_CODE.value if SUBJECT_CODE.fullmatch(t) else None


dp.add_operator(Settle("settle_geo_level", question="geo_level", test=_geo, cost=0))
dp.add_operator(Settle("settle_code_kind", question="code_kind", test=_code, cost=0))

# preference: settle by pattern before paying for an LLM call; then a stable question order
_order = {q: i for i, q in enumerate(QUESTIONS)}
dp.add_action_evaluator(
    sorting_evaluator(
        lambda a, s, io: (cast(NamedObject, a).params["cost"], _order[cast(NamedObject, a).params["question"]]),
        name="cheapest_first",
    )
)


def investigate(m: Mention, llm: object, trials: int, timeout: int) -> Mention:
    """Wrapper: run the sub-DP for one mention; returns the same mention with answers filled in"""
    dp.reinit()
    dp.state.mention = m
    dp(suppress_errors=False, llm=llm, trials=trials, timeout=timeout)
    return m
