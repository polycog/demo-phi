# PHI review demo: `cognition` vs. LLM

A design-partner demo of [polycog `cognition`](https://cognition.polycog.ai) applied to finding
protected health information (PHI) in a biotech clinical-trial packet, under **HIPAA Safe Harbor**
(45 CFR §164.514(b)(2)).

**Design approach:** the LLM proposes *situations*, while typed knowledge and deterministic
decision processes settle them, with a citation and evidence for every call.

## Results

(Raw results in the `out` folder.)

* [Summary of 5 comparison runs using 4 language models](out/summary.md)

### Local Models
* OSS-GPT-20B
  * [Run 1](https://htmlpreview.github.io/?https://github.com/polycog/demo-phi/blob/main/out/report_gpt-oss-20b-1.html)
  * [Run 2](https://htmlpreview.github.io/?https://github.com/polycog/demo-phi/blob/main/out/report_gpt-oss-20b-2.html)
* [OSS-GPT-120B](https://htmlpreview.github.io/?https://github.com/polycog/demo-phi/blob/main/out/report_gpt-oss-120b.html)

### Cloud Models
* [gpt-5-nano](https://htmlpreview.github.io/?https://github.com/polycog/demo-phi/blob/main/out/report_gpt-5-nano.html)
* [claude-sonnet-5-5](https://htmlpreview.github.io/?https://github.com/polycog/demo-phi/blob/main/out/report_sonnet-55.html)

## Run it

You only need [uv](https://docs.astral.sh/uv/). The first `uv run` creates `.venv` and installs the
dependencies from `pyproject.toml` / `uv.lock` (Python 3.13+).

```bash
uv run python -m pii_demo check
```

```bash
uv run python -m pii_demo run
```

```bash
open out/report.html
```

For Anthropic models, add the extra to every command, e.g. `uv run --extra anthropic python -m pii_demo run ...`.
A plain `uv run` removes extras again.

The model is chosen with arguments or environment variables (see `pii_demo/llm.py`):

| | default | examples |
|---|---|---|
| `--model` / `PII_MODEL` | `openai/gpt-oss-20b` | `gpt-5-mini`, or any Pydantic AI string with `--base-url ""`: `anthropic:claude-sonnet-5-5` |
| `--base-url` / `PII_BASE_URL` | `http://localhost:1234/v1` (LM Studio) | `""` = the provider's own endpoint |
| `PII_API_KEY` | `local` | falls back to `OPENAI_API_KEY` |

Other options: `--trials 3` (LLM votes per question; their agreement is the confidence),
`--min-confidence 0.6`, `--policy safe-harbor|conservative`, `--no-baseline`, `-v` (cognition logs).

Change the policy **without calling the LLM again**: only the rules stage reruns.

```bash
uv run python -m pii_demo redecide --policy conservative --save-as out/conservative
```

## The packet (`corpus/`)

Four short synthetic documents from a fictional Phase 2 study, NX-301: an enrollment log, a
serious-adverse-event narrative, a monitoring visit note and a central-lab sample manifest.
`corpus/gold.json` holds the expected treatment of 50 spans, each with the reason and the
"trap" it tests.

## The traps: where reading the text is not enough

| Situation | Why a single prompt struggles | What `cognition` does |
|---|---|---|
| `03608` vs `04970` | Whether a ZIP keeps its first 3 digits depends on a **population table** | `RestrictedZip`/`Zip3` rules consult the HHS list (`reference.py`) |
| `EM-19340822`, `4471902-LFT1` | These look like ordinary sample IDs. They are built from a birth date and an MRN that appear **only in another document** | `LINK` builds subject profiles in a `WorldGraph`; `DerivedCode` checks every code against them, and cites where each fact came from |
| `1934-08-22`, `91-year-old`, `92` | Over 89 even the **year** must go: that takes arithmetic against a reference year | `BirthDateOver89`, `AgeOver89` |
| `Dr. Priya Raman`, `Jamie Ortiz` | Safe Harbor covers the individual, relatives, employers and household, **not staff**. LLMs tend to redact every name | The general `AnyPersonName` rule and its exception `StaffOutOfScope` are both proposed; a **policy evaluator** picks one |
| `NX301-0007` | Random study codes are *permitted* re-identification codes (§164.514(c)) | `StudyCode` keeps them, but only if `DerivedCode` found nothing |
| `2026-06-18` (monitoring visit), `2026-03-05` (shipment) | Dates about the site or shipment are not about an individual; dates of admission or collection are | The LLM answers one narrow question, *what is this the date of?*, and a rule applies the regulation |
| `Wilson's disease`, `HeLa` | Names that are not people | `NotAPerson`, `BiomedicalTerm` |
| `1998 Boston Marathon finish at age 64` | Not on the list of 18, yet it identifies her and implies a 1934 birth year | `UniqueCharacteristic` **escalates** to a human, with the computed age as evidence |

## How it maps onto the library

```
Cogent "phi-reviewer"         sensor: packet (reads corpus/)   actuators: say, publish
└─ root DecisionProcess       one visible step per cycle (pipeline.py)
   EXTRACT      ModelPopulator(Extraction)            ← LLM proposes typed spans; regexes add cheap ones
   INVESTIGATE  sub-DP assess/investigate.py          ← decides WHICH questions to ask about each span
                  Ask(question) ── EnumClassifier     ← LLM answers typed questions, N votes = confidence
                  Settle(question)                    ← pattern answers; evaluator prefers it (no LLM cost)
   LINK         WorldGraph: Mention, Subject, Document, InDocument, Concerns
   DECIDE       sub-DP assess/rules.py                ← no LLM: 24 Safe Harbor rules as operators
                  guards: LowConfidence, UniqueCharacteristic → ESCALATE
                  policy evaluator: "most specific rule" (safe-harbor) | "most protective rule" (conservative)
   PUBLISH      actuator → results.json → report.html
```

Design choices worth pointing out to a design partner:

- **The LLM never decides.** It fills typed schemas and answers enum questions. A low-agreement
  answer is not acted on: it becomes an `ESCALATE` with the reason attached.
- **Investigate before deciding.** Every fact from every document is in the graph before any rule
  runs. That is what catches codes derived from identifiers in other documents.
- **Rules say what is allowed; policies say what is preferred.** Both general rules and their exceptions are
  proposed, and swapping one evaluator turns Safe Harbor into a stricter in-house policy. See
  `POLICIES` in `assess/rules.py`.
- **Every decision is explainable.** The rule, its CFR citation, the evidence (including which
  document a fact came from) and every rule that competed for the span are all in the report's
  decision trace.
- **Fair baseline.** The baseline (`baseline.py`) uses the same model *and the same rulebook*,
  including the restricted ZIP3 list, in one prompt per document. The comparison isolates
  process from knowledge.

## Layout

```
pii_demo/
  __main__.py        CLI: check | run | redecide | report
  llm.py             model selection (any Pydantic AI model)
  domain.py          typed vocabulary (DocEnums the LLM answers in), graph entities, Decision
  reference.py       restricted ZIP3 list, CFR citations, patterns
  extract.py         System 1 proposals: ModelPopulator + regex sensors, span resolution
  assess/investigate.py   sub-DP: which questions, asked how
  assess/rules.py         sub-DP: Safe Harbor rules + policy evaluators
  pipeline.py        root DP + Cogent
  baseline.py        single-prompt LLM baseline
  score.py, report.py
corpus/              synthetic packet + gold.json
```

## Caveats

- This is a demo, not a compliance tool. The synthetic packet and gold labels encode one reasonable
  reading of Safe Harbor.
- The restricted ZIP3 list comes from HHS guidance based on the 2000 Census.
- Subject attribution is "the nearest preceding subject code", which is fine for this packet. A
  real system would ask the LLM, or use document structure.
