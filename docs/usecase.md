# Problem Statement and Opportunity

## Problem statement

### Why organizations redact personal information

Organizations routinely share their data with vendors, partners, auditors and regulators as part of their everyday processes: a hospital sends records to a billing contractor, a bank answers a regulator's request, a sponsor sends trial documents to a lab, a company produces emails in litigation. Before it is shared, the personally identifiable information (PII) in it must be removed or transformed. What counts as PII, and what must happen to it, is set by the rules that govern the data: [HIPAA](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html) for health information in the US, [GDPR](https://gdpr-info.eu/) for personal data in the EU, state privacy laws such as the [CCPA](https://oag.ca.gov/privacy/ccpa), sector rules for financial and education records, and the contracts and in-house policies layered on top of them.

### What makes redaction hard

Redaction is hard because the decision about a span rarely depends on the span alone:

- **Context decides what is personal.** The same name may belong to a patient, who must be protected, or to the clinician treating them, who may not need to be. The same date may be a birth date or the date a shipment left a warehouse.
- **The rules are specific, and they differ by regime.** They say not only what to remove but what may stay, and in what form: a year instead of a full date, a region instead of an address, an age band instead of an age. They also carry exceptions that override the general rule.
- **Identifiers hide in combinations and across documents.** Facts that are harmless alone identify someone together: ZIP code, birth date and sex [are enough to single out most Americans](https://dataprivacylab.org/projects/identifiability/paper1.pdf). An internal code can be built from a record number that appears only in another file.
- **Both kinds of error are costly.** A missed identifier is a breach that can expose a person and the organization. Over-redaction destroys the data's value, and a process that flags everything for review saves no one any time.
- **Every decision must be defensible.** An auditor, regulator or opposing counsel may ask why a span was kept, and "the model thought so" is not an answer.

### How redaction is done today

Most organizations combine manual review with pattern-matching or named-entity tools. Patterns find well-formed identifiers such as phone numbers, emails and account numbers; entity recognizers find names and places. Neither knows the rules: they can't tell whose name it is, whether a date is about a person, or whether a code was derived from something personal. So people still read every document. That is slow, varies from reviewer to reviewer, and is easy to get wrong on a long, cross-referenced set of documents.

### An example: PHI in clinical-trial documents

This demo takes one demanding instance of the problem: protected health information (PHI) in clinical-trial documents. Biotech sponsors routinely share enrollment logs, serious-adverse-event narratives, monitoring notes and lab manifests with contract research organizations, central labs, partners and regulators. Before they do, the [HIPAA Safe Harbor method](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html) (45 CFR §164.514(b)(2)) requires removing 18 kinds of identifier of the individual, and of their relatives, employers and household members. The list reads simply, but applying it shows every difficulty above:

- **Names** must go, but only those of the individual and the people around them. Investigators, coordinators and other staff are out of scope.
- **Places smaller than a state** must go. The first three digits of a ZIP code may stay, but only if that three-digit area has more than 20,000 people; otherwise they become `000`.
- **Dates** directly related to the individual (birth, admission, discharge, sample collection) must be reduced to the year. A date about a site visit or a shipment is not about an individual and may stay.
- **Ages over 89**, and every element of a date that implies one, *including the year*, must be aggregated into "90 or older".
- **Record numbers, account numbers and any other unique identifying number, characteristic or code** must go. A study's own re-identification codes are permitted (§164.514(c)), but only if they are not derived from information about the individual. A sample labeled `4471902-LFT1` looks like an ordinary lab ID, unless the reviewer remembers that `4471902` is a medical record number listed in a different document.

## Opportunity and challenge

An automated reviewer could read every document in a set, decide each span under the applicable rules, explain each decision, and hand people only the cases that need judgment. The challenge is to do this without trading one kind of error for the other: it must not leak an identifier, must not strip out what the rules allow to stay, and must be able to show, for every span, which rule applied and why.

## Why this needs neurosymbolic AI

### Why LLMs can't do this alone

LLMs are the current state of the art for reading text in context: they can tell a patient's daughter from a study coordinator, an admission date from a shipment date, and an eponym such as "Wilson's disease" from a person. But asked "remove the personal information from this document", an LLM:

- **can't reliably apply tables and arithmetic,** such as checking a ZIP code against a population list, or working out that a 1934 birth date means the year must go too, even when the list and the rules are in the prompt;
- **reads one document at a time,** so it misses an identifier built from a fact that appears only in another document;
- **redacts by plausibility,** removing every name it sees, including those the rules leave in place;
- **varies from run to run,** with the same model, settings and input;
- **can't show why it made a call:** its explanation is generated after the answer, not the reason for it.

In this demo's comparison, a single-prompt LLM given the full Safe Harbor rulebook scored between 20/50 and 47/50 depending on the model, and on one model moved from 20 to 30 between two identical runs. See [the results summary](../out/summary.md).

### What symbolic reasoning adds

Adding symbolic reasoning keeps the LLM reading the text, and applies the rules the way a careful privacy reviewer does: first establish what each mention is, then apply the rule.

- **The LLM never decides.** It proposes spans and answers narrow, typed questions ("whose name is this?", "what is this the date of?"); rules apply the regulation to the answers.
- **Every document is read before any decision is made,** so an identifier built from a fact in another document is recognized as one.
- **Tables and arithmetic are exact:** reference lists are looked up, and ages are computed, not estimated.
- **Rules are separate from policy.** The regulation says which treatments are allowed; a policy says which is preferred, so an organization can adopt a stricter in-house policy, or apply the approach under a different regime, by changing the rules and policies rather than re-prompting.
- **Uncertainty goes to a human.** When the LLM's answers disagree, or no rule covers a span, the span is escalated with the reason attached.
- **Every decision is auditable:** the rule, its citation, the evidence, and the document each fact came from.

| Neural: reading the text | Symbolic: applying the rules |
|---|---|
| Propose candidate spans (names, dates, places, codes …) | Choose which questions to ask about each span |
| Answer narrow typed questions, several times, so agreement is a confidence | Build a profile of each individual across all documents |
| | Apply each rule of the regime, with its citation |
| | Pick among competing rules by policy; escalate what no rule can settle |

## Impact

On the clinical-trial packet, across five runs on four models, the neurosymbolic reviewer scored 48–50 out of 50 on every model, while the single-prompt baseline ranged from 20 to 47. The smallest local model with `cognition` (gpt-oss-20b) beat the strongest model on its own. Accuracy that doesn't depend on a frontier model means a reviewer like this can run on a small model inside the organization, so the personal data never has to leave it to be cleaned, and staff spend their time on the few escalated spans rather than on every page. The same design carries over to other regimes: the LLM's job (reading context) stays the same, and the rules and policies change.

## Technical approach

See [the technical approach](approach.md) for how an agent with cognition inside meets this challenge.
