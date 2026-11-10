"""
The root cogent: reads a document packet, and runs one visible step per DP cycle.

  EXTRACT      LLM proposes spans per document             (System 1, one document per cycle)
  INVESTIGATE  sub-DP asks typed questions about each span (one span per cycle)
  LINK         world graph: who is each span about, and what do we now know about each subject
  DECIDE       sub-DP applies Safe Harbor rules + policy  (one span per cycle; no LLM)
  PUBLISH      actuator writes the results

Splitting INVESTIGATE from DECIDE is what makes cross-document reasoning possible:
every fact from every document is in the graph before any rule runs.
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from cognition import Cogent, DecisionProcess, IOContainer, Operator, WorldGraph, create_actuator, create_sensor

from .assess import investigate as inv
from .assess import rules
from .domain import CodeKind, Concerns, DateRole, Decision, Document, InDocument, Mention, MentionKind, Subject, Whose
from .extract import extract


class Stage(Enum):
    EXTRACT = "extract"
    INVESTIGATE = "investigate"
    LINK = "link"
    DECIDE = "decide"
    PUBLISH = "publish"


@dataclass
class Packet:
    stage: Stage = Stage.EXTRACT
    to_extract: list[str] = field(default_factory=list)
    mentions: list[Mention] = field(default_factory=list)
    n_investigated: int = 0
    world: WorldGraph = field(default_factory=WorldGraph)
    decisions: list[Decision] = field(default_factory=list)
    considered: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    started: bool = False


dp = DecisionProcess(Packet)


def _timed(state: Packet, stage: str, t0: float) -> None:
    state.timings[stage] = state.timings.get(stage, 0.0) + time.perf_counter() - t0


@dp.operator("load")
class Load(Operator[Packet]):
    def can_perform(self, state: Packet, io: IOContainer) -> bool:
        return not state.started

    def perform(self, state: Packet, io: IOContainer) -> None:
        state.to_extract = sorted(io.i.packet)
        state.started = True


@dp.operator("extract_next")
class ExtractNext(Operator[Packet]):
    def can_perform(self, state: Packet, io: IOContainer) -> bool:
        return state.started and state.stage is Stage.EXTRACT and bool(state.to_extract)

    def perform(self, state: Packet, io: IOContainer) -> None:
        t0, name = time.perf_counter(), state.to_extract.pop(0)
        text = io.i.packet[name]
        doc = state.world.add_entity(Document(name=name, title=text.splitlines()[0])).e
        found, notes = extract(name, text, io.a.llm, int(io.a.timeout))
        for m in found:
            state.world.add_relation(InDocument(entity1=state.world.add_entity(m).e, entity2=doc))
        state.mentions.extend(found)
        state.notes.extend(f"{name}: {n}" for n in notes)
        _timed(state, "extract", t0)
        io.o.say(f"[extract] {name}: {len(found)} spans ({time.perf_counter() - t0:.1f}s)")


@dp.operator("investigate_next")
class InvestigateNext(Operator[Packet]):
    def can_perform(self, state: Packet, io: IOContainer) -> bool:
        return state.stage is Stage.INVESTIGATE and state.n_investigated < len(state.mentions)

    def perform(self, state: Packet, io: IOContainer) -> None:
        t0, m = time.perf_counter(), state.mentions[state.n_investigated]
        inv.investigate(m, io.a.llm, int(io.a.trials), int(io.a.timeout))
        state.world.add_entity(m)  # re-adding by name updates the node
        state.n_investigated += 1
        _timed(state, "investigate", t0)
        answers = ", ".join(f"{q}={a}" for q, a in m.answers.items() if not q.endswith("_by")) or "-"
        io.o.say(f"[investigate {state.n_investigated}/{len(state.mentions)}] {m.text!r} ({m.kind.value}): {answers}")


@dp.operator("link")
class Link(Operator[Packet]):
    """Turn per-span answers into per-subject knowledge, across all documents"""

    def can_perform(self, state: Packet, io: IOContainer) -> bool:
        return state.stage is Stage.LINK

    def perform(self, state: Packet, io: IOContainer) -> None:
        subjects: dict[str, Subject] = {}
        for m in state.mentions:
            if not m.subject_code:
                continue
            subj = subjects.setdefault(m.subject_code, Subject(name=m.subject_code))
            facts = {
                "names": m.kind is MentionKind.PERSON_NAME and m.answers.get("whose") == Whose.SUBJECT.value,
                "birth_dates": m.kind is MentionKind.DATE and m.answers.get("date_role") == DateRole.BIRTH.value,
                "record_numbers": m.kind is MentionKind.ID_CODE
                and m.answers.get("code_kind") == CodeKind.MEDICAL_RECORD_NUMBER.value,
            }
            for attr, holds in facts.items():
                if holds and m.text not in getattr(subj, attr):
                    getattr(subj, attr).append(m.text)
                    subj.learned_from.append(f"{m.text} <- {m.doc}")
        for subj in subjects.values():
            state.world.add_entity(subj)
        for m in state.mentions:
            if m.subject_code in subjects:
                state.world.add_relation(
                    Concerns(entity1=state.world.get_entity(m.name).e, entity2=state.world.get_entity(m.subject_code).e)
                )
        for subj in subjects.values():
            io.o.say(
                f"[link] {subj.name}: names={subj.names} birth={subj.birth_dates} mrn={subj.record_numbers}"
            )
        state.stage = Stage.DECIDE


@dp.operator("decide_next")
class DecideNext(Operator[Packet]):
    def can_perform(self, state: Packet, io: IOContainer) -> bool:
        return state.stage is Stage.DECIDE and len(state.decisions) < len(state.mentions)

    def perform(self, state: Packet, io: IOContainer) -> None:
        t0, m = time.perf_counter(), state.mentions[len(state.decisions)]
        subjects = {s.name: s for s in state.world.entities if isinstance(s, Subject)}
        decision, considered = rules.decide(
            io.a.rules_dp,
            m,
            subjects,
            policy=io.a.policy,
            ref_year=io.a.ref_year,
            min_confidence=io.a.min_confidence,
        )
        state.decisions.append(decision)
        state.considered[m.name] = considered
        _timed(state, "decide", t0)


@dp.operator("advance")
class Advance(Operator[Packet]):
    """Move to the next stage once the current one has nothing left to do"""

    def can_perform(self, state: Packet, io: IOContainer) -> bool:
        return state.started and (
            (state.stage is Stage.EXTRACT and not state.to_extract)
            or (state.stage is Stage.INVESTIGATE and state.n_investigated == len(state.mentions))
            or (state.stage is Stage.DECIDE and len(state.decisions) == len(state.mentions))
        )

    def perform(self, state: Packet, io: IOContainer) -> None:
        order = list(Stage)
        state.stage = order[order.index(state.stage) + 1]


@dp.operator("publish", terminal=True)
class Publish(Operator[Packet]):
    def can_perform(self, state: Packet, io: IOContainer) -> bool:
        return state.stage is Stage.PUBLISH

    def perform(self, state: Packet, io: IOContainer) -> None:
        io.o.publish(state)


def read_packet(folder: Path) -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted(folder.glob("*.txt"))}


def run(folder: Path, llm: Any, *, policy: str, trials: int, timeout: int, min_confidence: float, ref_year: int) -> Packet:
    """Build the cogent around the root DP and run it once over the packet"""
    published: list[Packet] = []
    agent = Cogent(dp, name="phi-reviewer")
    agent.add_sensor(create_sensor("packet", lambda: read_packet(folder)))
    agent.add_actuator(create_actuator("say", lambda msg: print(msg, file=sys.stderr, flush=True)))
    agent.add_actuator(create_actuator("publish", published.append))
    agent(
        llm=llm,
        rules_dp=rules.build(policy),
        policy=policy,
        trials=trials,
        timeout=timeout,
        min_confidence=min_confidence,
        ref_year=ref_year,
    )
    return published[0]


def redecide(packet: Packet, *, policy: str, min_confidence: float, ref_year: int) -> Packet:
    """Re-run only the DECIDE stage (no LLM) under a different policy, reusing everything learned"""
    rules_dp = rules.build(policy)
    subjects = {s.name: s for s in packet.world.entities if isinstance(s, Subject)}
    packet.decisions, packet.considered = [], {}
    for m in packet.mentions:
        d, c = rules.decide(rules_dp, m, subjects, policy=policy, ref_year=ref_year, min_confidence=min_confidence)
        packet.decisions.append(d)
        packet.considered[m.name] = c
    return packet
