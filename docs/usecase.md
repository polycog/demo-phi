# Problem Statement and Opportunity

## Problem statement

### What Safe Harbor requires

Biotech sponsors routinely share clinical-trial documents (enrollment logs, serious-adverse-event narratives, monitoring notes, lab manifests) with contract research organizations, central labs, partners and regulators. Before a packet leaves the organization, its protected health information (PHI) must be removed. Under the [HIPAA Safe Harbor method](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html) (45 CFR §164.514(b)(2)), that means removing 18 kinds of identifier of the individual, and of their relatives, employers and household members. The list reads simply, but applying it does not:

- **Names** must go, but only those of the individual and the people around them. Investigators, coordinators and other staff are out of scope.
- **Places smaller than a state** must go. The first three digits of a ZIP code may stay, but only if that three-digit area has more than 20,000 people; otherwise they become `000`.
- **Dates** directly related to the individual (birth, admission, discharge, sample collection) must be reduced to the year. A date about a site visit or a shipment is not about an individual and may stay.
- **Ages over 89**, and every element of a date that implies one, *including the year*, must be aggregated into "90 or older".
- **Record numbers, account numbers and any other unique identifying number, characteristic or code** must go. A study's own re-identification codes are permitted (§164.514(c)), but only if they are not derived from information about the individual.

### How packets are reviewed today

Today, privacy and clinical-operations staff read each document and redact by hand, sometimes helped by pattern-matching tools. Patterns find phone numbers and email addresses, but not the context Safe Harbor turns on: whether "Dr. Priya Raman" is a patient or the principal investigator, whether `2026-03-04` is a collection date or a shipment date, whether "Wilson's disease" names anyone. The hardest cases span documents. A sample labeled `4471902-LFT1` looks like an ordinary lab ID unless the reviewer remembers that `4471902` is a medical record number listed in a different document. Manual review is slow, varies from reviewer to reviewer, and is easy to get wrong on a long packet.

## Opportunity and challenge

An automated PHI reviewer could read the whole packet, decide each span, explain each decision, and hand a human only the cases that need judgment. But the cost of error runs in both directions. A missed identifier is a HIPAA breach and can re-identify a trial participant. Over-redaction strips the dates and staff names that safety reviewers and monitors need, and a reviewer that flags everything saves no one any time. The reviewer must also be auditable: a privacy officer has to be able to show why each span was kept or removed.

## Why this needs neurosymbolic AI

### Why LLMs can't do this alone

LLMs are the current state of the art for reading clinical prose in context: they can tell a patient's daughter from a study coordinator, an admission date from a shipment date, and an eponym from a person. But asked "remove the PHI from this document", an LLM:

- **can't reliably apply tables and arithmetic,** such as checking a ZIP code against the restricted list, or working out that a 1934 birth date means the year must go too, even when the list and the rules are in the prompt;
- **reads one document at a time,** so it misses a code built from an identifier that appears only in another document;
- **redacts by plausibility,** removing every name it sees, including staff names the regulation leaves in place;
- **varies from run to run,** with the same model, settings and packet;
- **can't show why it made a call:** its explanation is generated after the answer, not the reason for it.

In this demo's comparison, a single-prompt LLM given the full rulebook scored between 20/50 and 47/50 depending on the model, and on one model moved from 20 to 30 between two identical runs. See [the results summary](../out/summary.md).

### What symbolic reasoning adds

Adding symbolic reasoning keeps the LLM reading the text, and applies the regulation the way a careful privacy officer does: first establish what each mention is, then apply the rule.

- **The LLM never decides.** It proposes spans and answers narrow, typed questions ("what is this the date of?"); rules apply the regulation to the answers.
- **Every document is read before any decision is made,** so a code built from an identifier in another document is recognized as one.
- **Tables and arithmetic are exact:** the restricted ZIP list is looked up, and ages are computed against a reference year.
- **Policy is separate from the rules.** The regulation says which treatments are allowed; a policy says which is preferred, so an organization can adopt a stricter in-house policy without rewriting a single rule.
- **Uncertainty goes to a human.** When the LLM's answers disagree, or no rule covers a span, the span is escalated with the reason attached.
- **Every decision is auditable:** the rule, its CFR citation, the evidence and the document each fact came from.

| Neural: reading the text | Symbolic: applying the regulation |
|---|---|
| Propose candidate spans (names, dates, places, codes …) | Choose which questions to ask about each span |
| Answer narrow typed questions, several times, so agreement is a confidence | Build a profile of each participant across all documents |
| | Apply 21 Safe Harbor rules, each citing its CFR paragraph |
| | Pick among competing rules by policy; escalate what no rule can settle |

## Impact

Across five runs on four models, the neurosymbolic reviewer scored 48–50 out of 50 on every model, while the single-prompt baseline ranged from 20 to 47. The smallest local model with `cognition` (gpt-oss-20b) beat the strongest model on its own. Accuracy that doesn't depend on a frontier model means the reviewer can run on a small model inside the organization, so PHI need not leave it, and staff spend their time on the few escalated spans rather than on every page.

## Technical approach

See [the technical approach](approach.md) for how an agent with cognition inside meets this challenge.
