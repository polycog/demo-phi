"""
Self-contained HTML report: scorecard, where each approach fails, released documents,
and the full decision trace for every span.
"""

from collections import defaultdict
from html import escape

from .domain import Action, Decision
from .score import GoldHit, summarize

TRAPS = {
    "zip3-data": "ZIP3 needs population data",
    "age-90": "Age over 89, incl. birth year",
    "derived-code": "Code built from identifiers in another document",
    "reid-code": "Random study codes are allowed",
    "staff-not-subject": "Staff names are out of scope",
    "relative": "Relatives' names",
    "employer": "Employer names",
    "admin-date": "Dates not about an individual",
    "eponym": "Eponyms and cell lines",
    "unique-characteristic": "Unique characteristic needs review",
}

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a66;--card:#fff;--line:#e4e1da;--accent:#2f5d50;
--keep:#e8efe9;--gen:#fdf0d5;--red:#f6dcd8;--esc:#e3def5;--good:#2f7d4f;--bad:#b3392f;--warn:#a26a00}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--fg:#ecebe6;--muted:#a19f98;
--card:#1f1f1d;--line:#33322f;--accent:#8fc2b2;--keep:#24332b;--gen:#3b3220;--red:#40261f;--esc:#2f2a44;
--good:#6fcf97;--bad:#f08a7e;--warn:#e0b357}}
:root[data-theme=dark]{--bg:#161615;--fg:#ecebe6;--muted:#a19f98;--card:#1f1f1d;--line:#33322f;--accent:#8fc2b2;
--keep:#24332b;--gen:#3b3220;--red:#40261f;--esc:#2f2a44;--good:#6fcf97;--bad:#f08a7e;--warn:#e0b357}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,
"Segoe UI",sans-serif}main{max-width:1100px;margin:0 auto;padding:32px 16px 80px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:40px 0 10px;border-bottom:1px solid var(--line);
padding-bottom:6px}h3{font-size:15px;margin:22px 0 8px}.muted{color:var(--muted)}code,.mono{font-family:
ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.big{font-size:30px;font-weight:650}.good{color:var(--good)}.bad{color:var(--bad)}.warn{color:var(--warn)}
table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);border-radius:8px;
overflow:hidden}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
.scroll{overflow-x:auto}.doc{white-space:pre-wrap;background:var(--card);border:1px solid var(--line);
border-radius:8px;padding:14px;font-family:ui-monospace,Menlo,monospace;font-size:13px;line-height:1.7}
mark{border-radius:4px;padding:1px 3px;color:inherit}.a-KEEP{background:transparent;border-bottom:2px dotted
var(--good)}.a-GENERALIZE{background:var(--gen)}.a-REDACT{background:var(--red)}.a-ESCALATE{background:var(--esc)}
.pill{display:inline-block;font-size:11px;font-weight:650;padding:1px 7px;border-radius:99px}
.p-KEEP{background:var(--keep)}.p-GENERALIZE{background:var(--gen)}.p-REDACT{background:var(--red)}
.p-ESCALATE{background:var(--esc)}.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:760px){.two{grid-template-columns:1fr}}details{margin:4px 0}summary{cursor:pointer}
ul.ev{margin:4px 0 0 18px;padding:0}.ok:before{content:"✓ ";color:var(--good)}.no:before{content:"✗ ";color:var(--bad)}
.legend mark{margin-right:8px}
"""


def _pill(a: Action | str) -> str:
    v = a.value if isinstance(a, Action) else a
    return f'<span class="pill p-{v}">{v}</span>'


def _released(text: str, decisions: list[Decision]) -> str:
    out, pos = [], 0
    for d in sorted(decisions, key=lambda d: (d.start, -(d.end - d.start))):
        if d.start < pos:
            continue
        out.append(escape(text[pos : d.start]))
        tip = escape(f"{d.text} → {d.action.value} [{d.rule}] {d.rationale}", quote=True)
        shown = d.text if d.action is Action.KEEP else (d.replacement or "[REDACTED]")
        out.append(f'<mark class="a-{d.action.value}" title="{tip}">{escape(shown)}</mark>')
        pos = d.end
    out.append(escape(text[pos:]))
    return "".join(out)


def render(payload: dict, systems: dict[str, list[Decision]], results: dict[str, tuple[list[GoldHit], list[Decision]]]) -> str:
    names = list(systems)
    sums = {n: summarize(*results[n]) for n in names}
    h: list[str] = [
        "<!doctype html><html lang=en><head><meta charset=utf-8>",
        '<meta name=viewport content="width=device-width,initial-scale=1">',
        f"<title>PHI Review Demo</title><style>{CSS}</style></head><body><main>",
        "<h1>Finding PHI in a clinical-trial packet</h1>",
        f'<p class=muted>HIPAA Safe Harbor · policy <b>{escape(payload["policy"])}</b> · model <code>{escape(payload["model"])}</code>'
        f' · {payload["trials"]} votes per question · reference year {payload["ref_year"]}</p>',
        "<p>Both approaches use the <b>same model</b> and the <b>same rulebook</b>. The baseline asks the model to "
        "de-identify each document in one prompt. The <b>cognition</b> pipeline only asks the model to propose spans and "
        "answer narrow typed questions about them. A knowledge graph links facts across documents, and deterministic Safe Harbor rules make every "
        "decision, citing the regulation and their evidence.</p>",
    ]

    # --- scorecard
    h.append('<div class=cards>')
    for n in names:
        s, total = sums[n], sums[n]["gold spans"]
        correct = s.get("correct", 0)
        leaks, over = s.get("leak", 0), s.get("over-redaction", 0) + s.get("redactions outside gold", 0)
        other = total - correct - leaks - s.get("over-redaction", 0)
        h.append(
            f'<div class=card><div class=muted>{escape(n)}</div><div class=big>{correct}/{total}</div>'
            f'<div>spans treated correctly</div><div class="{"bad" if leaks else "good"}">{leaks} PHI leaks</div>'
            f'<div class="{"warn" if over else "good"}">{over} over-redactions</div>'
            f'<div class=muted>{other} other mismatches (wrong treatment, replacement or review)</div></div>'
        )
    t = payload.get("timings", {})
    h.append(
        f'<div class=card><div class=muted>cost</div><div>cognition: {t.get("cognition_total", 0):.0f}s</div>'
        f'<div class=muted>extract {t.get("extract", 0):.0f}s · questions {t.get("investigate", 0):.0f}s · rules {t.get("decide", 0):.2f}s</div>'
        + (f'<div>baseline: {t.get("baseline_total", 0):.0f}s</div>' if "baseline_total" in t else "")
        + "<div class=muted>The rules stage needs no LLM, so a policy change re-runs in milliseconds.</div></div></div>"
    )

    # --- by trap
    h.append("<h2>Where the text alone is not enough</h2><div class=scroll><table><tr><th>Situation</th>")
    h += [f"<th>{escape(n)}</th>" for n in names]
    h.append("</tr>")
    by_trap: dict[str, dict[str, list[GoldHit]]] = defaultdict(lambda: defaultdict(list))
    for n in names:
        for hit in results[n][0]:
            by_trap[hit.trap or "plain"][n].append(hit)
    for trap, label in list(TRAPS.items()) + [("plain", "Plain identifiers (names, phones, MRNs …)")]:
        if trap not in by_trap:
            continue
        h.append(f"<tr><td>{escape(label)}</td>")
        for n in names:
            hs = by_trap[trap][n]
            ok = sum(x.outcome == "correct" for x in hs)
            cls = "good" if ok == len(hs) else "bad"
            h.append(f'<td class="{cls}">{ok}/{len(hs)}</td>')
        h.append("</tr>")
    h.append("</table></div>")

    # --- mismatches
    h.append("<h2>Every mismatch with the expected answer</h2><div class=scroll><table><tr><th>Document</th><th>Span</th>"
             "<th>Expected</th>" + "".join(f"<th>{escape(n)}</th>" for n in names) + "<th>Why</th></tr>")
    keyed = {n: {(x.doc, x.start): x for x in results[n][0]} for n in names}
    for hit in results[names[0]][0]:
        row = [keyed[n][(hit.doc, hit.start)] for n in names]
        if all(r.outcome == "correct" for r in row):
            continue
        cells = "".join(
            f'<td class="{"ok" if r.outcome == "correct" else "no"}">{_pill(r.got)}'
            f'{" " + escape(r.replacement_got or "") if r.got is Action.GENERALIZE else ""}'
            f'<div class=muted>{escape(r.outcome)}</div></td>'
            for r in row
        )
        exp = _pill(hit.expected) + (f" {escape(hit.replacement_expected)}" if hit.replacement_expected else "")
        h.append(f"<tr><td class=mono>{escape(hit.doc)}</td><td class=mono>{escape(hit.text)}</td><td>{exp}</td>{cells}"
                 f"<td class=muted>{escape(hit.why)}</td></tr>")
    h.append("</table></div>")
    for n in names:
        extras = results[n][1]
        if extras:
            h.append(f"<p><b>{escape(n)}</b> also changed spans that should have stayed: " +
                     ", ".join(f"<code>{escape(d.text)}</code> ({d.action.value})" for d in extras) + "</p>")

    # --- knowledge graph
    h.append("<h2>What the graph learned about each subject</h2><p class=muted>Facts collected across documents "
             "before any rule ran. This is what lets a rule spot that <code>EM-19340822</code> in the SAE narrative "
             "or <code>4471902-LFT1</code> in the manifest is built from identifiers that only appear in the enrollment log.</p>")
    h.append("<div class=scroll><table><tr><th>Subject</th><th>Names</th><th>Birth dates</th><th>MRNs</th><th>Learned from</th></tr>")
    for s in payload.get("subjects", []):
        h.append(f"<tr><td class=mono>{escape(s['name'])}</td><td>{escape(', '.join(s['names']))}</td>"
                 f"<td>{escape(', '.join(s['birth_dates']))}</td><td>{escape(', '.join(s['record_numbers']))}</td>"
                 f"<td class=muted>{escape('; '.join(s['learned_from']))}</td></tr>")
    h.append("</table></div>")

    # --- documents
    h.append('<h2>Released documents</h2><p class="legend muted"><mark class=a-GENERALIZE>generalized</mark>'
             '<mark class=a-REDACT>redacted</mark><mark class=a-ESCALATE>held for review</mark>'
             '<mark class=a-KEEP>considered, kept</mark> Hover a span to see why.</p>')
    by_doc = {n: defaultdict(list) for n in names}
    for n in names:
        for d in systems[n]:
            by_doc[n][d.doc].append(d)
    mentions = {m["name"]: m for m in payload.get("mentions", [])}
    for doc, text in payload["documents"].items():
        h.append(f"<h3 class=mono>{escape(doc)}</h3><div class=two>")
        for n in names:
            h.append(f'<div><div class=muted>{escape(n)}</div><div class=doc>{_released(text, by_doc[n][doc])}</div></div>')
        h.append("</div>")
        # decision trace
        h.append("<details><summary>Decision trace for this document (cognition)</summary><div class=scroll><table>"
                 "<tr><th>Span</th><th>Decision</th><th>Rule · citation</th><th>Evidence</th><th>Rules that applied</th></tr>")
        for d, (mname, m) in zip(
            sorted(by_doc["cognition"][doc], key=lambda d: d.start),
            sorted(((k, v) for k, v in mentions.items() if v["doc"] == doc), key=lambda kv: kv[1]["start"]),
        ):
            comp = payload.get("considered", {}).get(mname, [])
            h.append(
                f"<tr><td class=mono>{escape(d.text)}</td><td>{_pill(d.action)} {escape(d.replacement or '')}</td>"
                f"<td><b>{escape(d.rule)}</b><div class=muted>{escape(d.citation)}</div>{escape(d.rationale)}</td>"
                f'<td><ul class=ev>{"".join(f"<li>{escape(e)}</li>" for e in d.evidence)}</ul></td>'
                f'<td class=mono>{"<br>".join(escape(c) for c in comp)}</td></tr>'
            )
        h.append("</table></div></details>")
        if "baseline" in names:
            h.append("<details><summary>Baseline's stated reasons</summary><ul>")
            for d in sorted(by_doc["baseline"][doc], key=lambda d: d.start):
                h.append(f"<li><code>{escape(d.text)}</code> {_pill(d.action)} {escape(d.replacement or '')} "
                         f"<span class=muted>{escape(d.rationale)}</span></li>")
            h.append("</ul></details>")

    if payload.get("notes"):
        h.append("<h2>Notes</h2><ul>" + "".join(f"<li class=muted>{escape(n)}</li>" for n in payload["notes"]) + "</ul>")
    h.append("</main></body></html>")
    return "\n".join(h)
