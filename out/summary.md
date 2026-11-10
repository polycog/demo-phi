# Cognition vs. baseline across models

Five runs of the same 4-document packet (50 gold spans, HIPAA Safe Harbor policy, 3 LLM votes per
question). In each run, both approaches used the same model and the same rulebook.

## Headline

**Cognition's accuracy barely depends on the model; the baseline's depends on it heavily.** Cognition
scored 48–50/50 on every model. The single-prompt baseline ranged from 20/50 to 47/50. Even the
smallest local model with cognition (gpt-oss-20b, 50/50 twice) beat the strongest model on its own
(Claude Sonnet 5.5 baseline, 47/50).

| Model | Where it ran | Cognition | Baseline (strict) | Baseline (lenient¹) | PHI leaks (cog · base) | Over-redactions² (cog · base) | Time (cog · base) |
|---|---|---|---|---|---|---|---|
| gpt-oss-20b, run 1 | local (LM Studio) | **50/50** | 20/50 | 21/50 | 0 · 15 | 2 · 8 | 184 s · 32 s |
| gpt-oss-20b, run 2 | local (LM Studio) | **50/50** | 30/50 | 36/50 | 0 · 3 | 1 · 10 | 170 s · 44 s |
| gpt-oss-120b | local (LM Studio) | **49/50** | 33/50 | 36/50 | 1 · 2 | 3 · 4 | 249 s · 54 s |
| gpt-5-nano | cloud (Azure OpenAI) | **48/50** | 29/50 | 32/50 | 1 · 2 | 3 · 17 | 774 s · 185 s |
| Claude Sonnet 5.5 | cloud (Anthropic) | **50/50** | 47/50 | 48/50 | 0 · 0 | 5 · 2 | 258 s · 22 s |

¹ *Lenient* also counts baseline answers that are right in substance but formatted differently from
the gold answer: `Enrolled 2025` for `2025`, `000` for `000**`, `admitted in 2026` for `2026`. It
also counts `90+` for the 1934 birth date, which Safe Harbor allows (see caveats). Cognition gains
nothing from leniency: its output always uses the gold format.
² Counted the same way the report counts them: gold spans that should have been kept, plus changes
to spans outside the gold list. Nearly all of cognition's are *escalations to human review*, not
silent redactions.

## Where each approach fails

Each cell is **cognition · baseline**, correct out of total.

| Situation | gpt-oss-20b (run 1) | gpt-oss-20b (run 2) | gpt-oss-120b | gpt-5-nano | Claude Sonnet 5.5 |
|---|---|---|---|---|---|
| ZIP3 needs population data | 2/2 · 0/2 | 2/2 · 0/2 | 2/2 · 0/2 | 2/2 · 0/2 | 2/2 · 2/2 |
| Age over 89, incl. birth year | 4/4 · 2/4 | 4/4 · 2/4 | 4/4 · 2/4 | 3/4 · 2/4 | 4/4 · 3/4 |
| Code built from identifiers in another document | 2/2 · 1/2 | 2/2 · 1/2 | 2/2 · 0/2 | 2/2 · 1/2 | 2/2 · 0/2 |
| Random study codes are allowed | 8/8 · 4/8 | 8/8 · 5/8 | 8/8 · 8/8 | 8/8 · 0/8 | 8/8 · 8/8 |
| Staff names are out of scope | 3/3 · 1/3 | 3/3 · 3/3 | 3/3 · 1/3 | 3/3 · 2/3 | 3/3 · 3/3 |
| Relatives' names | 2/2 · 2/2 | 2/2 · 2/2 | 2/2 · 2/2 | 2/2 · 2/2 | 2/2 · 2/2 |
| Employer names | 1/1 · 0/1 | 1/1 · 1/1 | 1/1 · 1/1 | 1/1 · 0/1 | 1/1 · 1/1 |
| Dates not about an individual | 5/5 · 4/5 | 5/5 · 5/5 | 5/5 · 4/5 | 5/5 · 5/5 | 5/5 · 5/5 |
| Eponyms and cell lines | 2/2 · 2/2 | 2/2 · 2/2 | 2/2 · 2/2 | 2/2 · 2/2 | 2/2 · 2/2 |
| Unique characteristic needs review | 1/1 · 0/1 | 1/1 · 0/1 | 0/1 · 0/1 | 0/1 · 0/1 | 1/1 · 1/1 |
| Plain identifiers (names, phones, MRNs …) | 20/20 · 4/20 | 20/20 · 9/20 | 20/20 · 13/20 | 20/20 · 15/20 | 20/20 · 20/20 |

## What the numbers say

1. **The rules-and-data situations separate the approaches most.** Only Sonnet's baseline got the
   ZIP3 cases right, even though every baseline prompt contained the restricted-ZIP list. No baseline
   caught both codes derived from identifiers in another document; it never sees the enrollment log
   when reading the narrative or the manifest. Cognition got all of these right on every model.
2. **With a frontier model the gap nearly closes on this packet.** Sonnet's baseline differs from
   cognition on only 3 spans:
   - the two derived codes, which it held for review instead of redacting. That's safe, but it
     couldn't say why they're identifiers;
   - the 1934 birth date, which it aggregated to `90+`. That's arguably acceptable.

   On a small, clean packet, a strong model's case for cognition rests less on raw accuracy than on
   cross-document reasoning, cited explanations, policy control, and getting the same quality from
   much cheaper models.
3. **The baseline isn't stable from run to run; cognition is.** The two gpt-oss-20b runs used the same
   model and settings. The baseline went from 20 to 30 correct, and from 15 leaks to 3: in run 1 it
   returned a single finding for the whole enrollment log. Cognition scored 50/50 both times.
4. **Cognition's only leak is always the same span, and it's an extraction miss.** On gpt-oss-120b and
   gpt-5-nano, the model never proposed "1998 Boston Marathon finish at age 64" as a unique
   characteristic, so no rule ever saw it. The weak point is the LLM's proposal step: rules can only
   judge spans the LLM proposes.
5. **Cognition's other errors cost reviewer time, not privacy.** Spans no rule recognizes go to review:
   "Site 04", "this summer", "two days earlier", and role words such as "CCRP", "Principal
   Investigator" and "daughter". Stronger models propose more spans, so they trigger more of these:
   Sonnet has the most, at 5. On gpt-5-nano there is one real bug: a document title was split around
   its date, and the leftover piece "from Site 04" was redacted. That comes from my span-splitting
   code, not the model.
6. **Cognition is 4–12× slower.** Almost all the time goes on the question stage (3 votes per
   question, one span at a time). The rules stage takes about 0.02 s per run.

## Caveats

- **The gold labels and the rules were generated.** Real data and rules would provide stronger
  empirical evidence.
- **The gold label for the 1934 birth date is probably too strict.** It expects REDACT, but Safe
  Harbor allows aggregating such ages into a "90 or older" category, so `90+` should also count as
  correct. That would add one point to most baselines.
- **The sample is small:** one packet of 50 spans, one run per model (two for gpt-oss-20b).
