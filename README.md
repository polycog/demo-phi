# PHI Reviewer

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![cognition](https://img.shields.io/badge/cognition-inside-7b2fbe?labelColor=f3effa&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjIgMCAzNiAzNiIgZmlsbD0ibm9uZSI+PHBvbHlnb24gcG9pbnRzPSIyMCw0IDM0LjMsMTQuNCAyOC44LDMxLjYgMTEuMiwzMS42IDUuNywxNC40IiBzdHJva2U9IiM3YjJmYmUiIHN0cm9rZS13aWR0aD0iMi4yIi8+PGcgc3Ryb2tlPSIjYzQ3ZDIwIiBzdHJva2Utd2lkdGg9IjIiPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjAiIHkyPSI0Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSIzNC4zIiB5Mj0iMTQuNCIvPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjguOCIgeTI9IjMxLjYiLz48bGluZSB4MT0iMjAiIHkxPSIyMCIgeDI9IjExLjIiIHkyPSIzMS42Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSI1LjciIHkyPSIxNC40Ii8+PC9nPjxnIGZpbGw9IiM3YjJmYmUiPjxjaXJjbGUgY3g9IjIwIiBjeT0iNCIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iMzQuMyIgY3k9IjE0LjQiIHI9IjMuMiIvPjxjaXJjbGUgY3g9IjI4LjgiIGN5PSIzMS42IiByPSIzLjIiLz48Y2lyY2xlIGN4PSIxMS4yIiBjeT0iMzEuNiIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iNS43IiBjeT0iMTQuNCIgcj0iMy4yIi8+PC9nPjxjaXJjbGUgY3g9IjIwIiBjeT0iMjAiIHI9IjQuNiIgZmlsbD0iI2M0N2QyMCIvPjwvc3ZnPgo=)](https://github.com/polycog/cognition)
[![cognition on PyPI](https://img.shields.io/pypi/v/polycog-cognition?label=cognition%20on%20PyPI&color=c47d20&labelColor=f3effa&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjIgMCAzNiAzNiIgZmlsbD0ibm9uZSI+PHBvbHlnb24gcG9pbnRzPSIyMCw0IDM0LjMsMTQuNCAyOC44LDMxLjYgMTEuMiwzMS42IDUuNywxNC40IiBzdHJva2U9IiM3YjJmYmUiIHN0cm9rZS13aWR0aD0iMi4yIi8+PGcgc3Ryb2tlPSIjYzQ3ZDIwIiBzdHJva2Utd2lkdGg9IjIiPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjAiIHkyPSI0Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSIzNC4zIiB5Mj0iMTQuNCIvPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjguOCIgeTI9IjMxLjYiLz48bGluZSB4MT0iMjAiIHkxPSIyMCIgeDI9IjExLjIiIHkyPSIzMS42Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSI1LjciIHkyPSIxNC40Ii8+PC9nPjxnIGZpbGw9IiM3YjJmYmUiPjxjaXJjbGUgY3g9IjIwIiBjeT0iNCIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iMzQuMyIgY3k9IjE0LjQiIHI9IjMuMiIvPjxjaXJjbGUgY3g9IjI4LjgiIGN5PSIzMS42IiByPSIzLjIiLz48Y2lyY2xlIGN4PSIxMS4yIiBjeT0iMzEuNiIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iNS43IiBjeT0iMTQuNCIgcj0iMy4yIi8+PC9nPjxjaXJjbGUgY3g9IjIwIiBjeT0iMjAiIHI9IjQuNiIgZmlsbD0iI2M0N2QyMCIvPjwvc3ZnPgo=)](https://pypi.org/project/polycog-cognition/)

## 1. Summary

A **neurosymbolic** reviewer for redacting personal information, built with the [`cognition`](https://github.com/polycog/cognition) library and demonstrated on protected health information in clinical trials. It reads a packet of clinical-trial documents, finds the protected health information (PHI) that HIPAA Safe Harbor (45 CFR §164.514(b)(2)) requires removing, and decides for each span whether to redact, generalize, keep, or escalate it to a human, citing the regulation and the evidence for every call. A single-prompt LLM baseline, given the same model and the same rulebook, runs alongside it for comparison.

### Contents

1. [Summary](#1-summary)
2. [Problem Statement](#2-problem-statement)
3. [Technical Approach and Results](#3-technical-approach-and-results)
4. [Install and Run](#4-install-and-run)
5. [License and Disclaimers](#5-license-and-disclaimers)

---

## 2. Problem Statement

Organizations routinely share their data with vendors, partners, auditors and regulators, and before they do, the personally identifiable information (PII) in it must be removed or transformed under rules such as HIPAA, GDPR or the CCPA. Today that means manual review, helped by pattern tools that find phone numbers but not the context the rules turn on: whose name it is, whether a date is about a person, or whether a code was built from an identifier in another document. This demo takes one demanding instance, protected health information (PHI) in clinical-trial documents under HIPAA Safe Harbor. Staff names may stay but a patient's daughter's may not, a ZIP code's first three digits may stay only if the area is populous enough, and a sample ID can be built from a medical record number listed in another document. LLMs can read that context, but they can't be trusted to apply tables and arithmetic exactly, to connect facts across documents, or to explain their calls. Both kinds of error are costly: a missed identifier is a breach, and over-redaction destroys the data's value. 

See [the full problem statement and opportunity](docs/usecase.md).

---

## 3. Technical Approach and Results

Like a careful privacy officer, the reviewer first establishes what each mention is, then applies the rule. An LLM only proposes candidate spans and answers narrow, typed questions about each one (*whose name is this? what is this the date of?*), several times, so that agreement among its answers is a confidence. A **[symbolic decision process](https://docs.polycog.ai/ideas/kadp.html)** built with `cognition` decides everything else: which questions to ask, a **[world graph](https://docs.polycog.ai/ideas/knowledge.html)** profile of each participant built from every document, and 21 Safe Harbor rules written as WHEN/THEN operators, with a swappable policy that picks among the rules that apply. With no LLM in these decisions, the same answers always lead to the same decision, and every step can be traced. See [the technical approach](docs/approach.md) for details.

**Results:** across five runs on four models, `cognition` scored 48–50/50 on every model, while the single-prompt baseline scored 20–47/50. Even the smallest local model with `cognition` beat the strongest model on its own. See [the summary of all runs](out/summary.md), or open a run's report:

| Model | Where it ran | Report |
|---|---|---|
| gpt-oss-20b | local (LM Studio) | [run 1](https://html.polycog.ai/?https://github.com/polycog/demo-phi/blob/main/out/report_gpt-oss-20b-1.html) · [run 2](https://html.polycog.ai/?https://github.com/polycog/demo-phi/blob/main/out/report_gpt-oss-20b-2.html) |
| gpt-oss-120b | local (LM Studio) | [report](https://html.polycog.ai/?https://github.com/polycog/demo-phi/blob/main/out/report_gpt-oss-120b.html) |
| gpt-5-nano | cloud (Azure OpenAI) | [report](https://html.polycog.ai/?https://github.com/polycog/demo-phi/blob/main/out/report_gpt-5-nano.html) |
| Claude Sonnet 5.5 | cloud (Anthropic) | [report](https://html.polycog.ai/?https://github.com/polycog/demo-phi/blob/main/out/report_sonnet-55.html) |

---

## 4. Install and Run

### 4.1 Clone the repository

```bash
git clone https://github.com/polycog/demo-phi.git
cd demo-phi
```

### 4.2 Install the dependencies

`cognition` requires **Python 3.13 or later**. The project is managed with [uv](https://docs.astral.sh/uv/): the first `uv run` creates `.venv` and installs everything in [`pyproject.toml`](pyproject.toml) and `uv.lock`. To install up front:

```bash
uv sync
```

This installs:

- **`polycog-cognition`**, the `cognition` library, published on PyPI under that name;
- **`pydantic-ai-slim[openai]`**, which `cognition` builds on, with the OpenAI extra for the language model.

For Anthropic models, add the `anthropic` extra to every command, e.g. `uv run --extra anthropic python -m pii_demo run ...`. A plain `uv run` removes extras again.

### 4.3 Choose a language model

The model is chosen with arguments or environment variables (see [`pii_demo/llm.py`](pii_demo/llm.py)):

| Setting | Default | Examples |
|---|---|---|
| `--model` / `PII_MODEL` | `openai/gpt-oss-20b` | `gpt-5-mini`, or any Pydantic AI model string with `--base-url ""`, such as `anthropic:claude-sonnet-5-5` |
| `--base-url` / `PII_BASE_URL` | `http://localhost:1234/v1` (LM Studio) | `""` for the provider's own endpoint |
| `PII_API_KEY` | `local` | falls back to `OPENAI_API_KEY` |

Export any API key in the shell you run the demo from, and keep it out of the repository. Check that the model is reachable:

```bash
uv run python -m pii_demo check
```

### 4.4 Run the review

```bash
uv run python -m pii_demo run         # add -v to log cognition's decisions
open out/report.html
```

`run` reviews the four documents in [`corpus/`](corpus), runs the baseline on the same model, scores both against `corpus/gold.json`, and writes `out/results.json` and `out/report.html`. Other options:

| Option | Default | What it does |
|---|---|---|
| `--trials` | `3` | LLM votes per question; their agreement is the confidence |
| `--min-confidence` | `0.6` | Below this agreement, a span is escalated instead of decided |
| `--policy` | `safe-harbor` | `safe-harbor` (most specific rule wins) or `conservative` (most protective rule wins) |
| `--no-baseline` | off | Skip the single-prompt baseline |

### 4.5 Change the policy without calling the LLM again

Only the rules stage reruns, so this takes a fraction of a second:

```bash
uv run python -m pii_demo redecide --policy conservative --save-as out/conservative
```

To re-score and re-render an existing `results.json`, run `uv run python -m pii_demo report`.

---

## 5. License and Disclaimers

This project is released under the [Apache License 2.0](LICENSE). Copyright © 2026 Polycog, Inc. If you use it, please cite it using the metadata in [`CITATION.cff`](CITATION.cff).

> **Disclaimer:** this project is a technical demonstration of neurosymbolic reasoning. It is not a compliance tool and is not legal advice. The documents in `corpus/` and the people in them are fictional, and the gold labels encode one reasonable reading of Safe Harbor. The restricted ZIP3 list comes from HHS guidance based on the 2000 Census. Participant attribution uses "the nearest preceding subject code", which suits this packet; a real system would ask the LLM or use the document's structure.
