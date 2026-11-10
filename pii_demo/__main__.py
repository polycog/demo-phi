"""
python -m pii_demo check                     # is the model endpoint reachable?
python -m pii_demo run [options]             # cognition pipeline + baseline -> out/results.json + out/report.html
python -m pii_demo redecide --policy conservative   # re-run only the rules on saved results (no LLM)
python -m pii_demo report                    # rebuild out/report.html from out/results.json
"""

import argparse
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

from .domain import Decision, Mention, Subject
from .llm import LLMConfig, api_key, make_model

ROOT = Path(__file__).resolve().parent.parent


def _say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def cmd_check(args: argparse.Namespace) -> None:
    cfg = LLMConfig.from_env(args.model, args.base_url)
    _say(f"model: {cfg.label}")
    if cfg.base_url:
        # informational only: some endpoints need a key for /models, some don't offer it at all
        from openai import OpenAI

        try:
            ids = sorted(m.id for m in OpenAI(base_url=cfg.base_url, api_key=api_key(), timeout=15).models.list())
            shown = ids if len(ids) <= 30 else ids[:30] + [f"... {len(ids) - 30} more"]
            _say(f"endpoint lists: {shown}")
            if cfg.model.removeprefix("openai:") not in ids:
                _say(f"!! {cfg.model!r} is not listed; pass --model with one of the ids above")
        except Exception as e:  # noqa: BLE001
            _say(f"(could not list models at {cfg.base_url}: {type(e).__name__}: {e}; trying the model anyway)")
    from pydantic_ai import Agent

    t0 = time.perf_counter()
    try:
        out = Agent(make_model(cfg)).run_sync("Reply with the single word: ready").output
    except Exception as e:  # noqa: BLE001
        import traceback

        _say(f"!! the model call failed: {type(e).__name__}: {e}")
        frame = traceback.extract_tb(e.__traceback__)[-1]
        _say(f"   raised in {frame.filename}:{frame.lineno} ({frame.name})")
        if args.verbose:
            traceback.print_exc()
        else:
            _say("   re-run with -v (before 'check') for the full traceback")
        sys.exit(1)
    _say(f"model replied {out!r} in {time.perf_counter() - t0:.1f}s")


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))


def cmd_run(args: argparse.Namespace) -> None:
    from . import baseline, pipeline

    cfg = LLMConfig.from_env(args.model, args.base_url)
    llm = make_model(cfg)
    docs = pipeline.read_packet(args.corpus)
    _say(f"model: {cfg.label} | policy: {args.policy} | trials: {args.trials} | docs: {len(docs)}")

    t0 = time.perf_counter()
    packet = pipeline.run(
        args.corpus, llm, policy=args.policy, trials=args.trials, timeout=args.timeout,
        min_confidence=args.min_confidence, ref_year=args.ref_year,
    )  # fmt: skip
    t_cog = time.perf_counter() - t0
    payload = {
        "model": cfg.label,
        "policy": args.policy,
        "trials": args.trials,
        "min_confidence": args.min_confidence,
        "ref_year": args.ref_year,
        "documents": docs,
        "mentions": [m.model_dump(mode="json") for m in packet.mentions],
        "subjects": [s.model_dump(mode="json") for s in packet.world.entities if isinstance(s, Subject)],
        "decisions": [d.model_dump(mode="json") for d in packet.decisions],
        "considered": packet.considered,
        "notes": packet.notes,
        "timings": {**packet.timings, "cognition_total": t_cog},
    }
    if not args.no_baseline:
        t0 = time.perf_counter()
        b, bt = baseline.run_baseline(docs, llm, ref_year=args.ref_year, timeout=args.timeout, say=_say)
        payload["baseline"] = [d.model_dump(mode="json") for d in b]
        payload["timings"]["baseline_total"] = time.perf_counter() - t0
    _save(args.out / "results.json", payload)
    _say(f"saved {args.out / 'results.json'}")
    _report(args.out, args.gold)


def cmd_redecide(args: argparse.Namespace) -> None:
    from cognition import WorldGraph

    from . import pipeline

    path = args.out / "results.json"
    payload = json.loads(path.read_text())
    packet = pipeline.Packet()
    packet.mentions = [Mention.model_validate(m) for m in payload["mentions"]]
    packet.world = WorldGraph()
    for s in payload["subjects"]:
        packet.world.add_entity(Subject.model_validate(s))
    pipeline.redecide(packet, policy=args.policy, min_confidence=args.min_confidence, ref_year=payload["ref_year"])
    payload.update(
        policy=args.policy, min_confidence=args.min_confidence,
        decisions=[d.model_dump(mode="json") for d in packet.decisions], considered=packet.considered,
    )  # fmt: skip
    target = args.out if args.save_as is None else args.save_as
    _save(target / "results.json", payload)
    _report(target, args.gold)


def _report(out: Path, gold: Path) -> None:
    from . import report, score

    payload = json.loads((out / "results.json").read_text())
    g = score.load_gold(gold, payload["documents"])
    systems = {"cognition": [Decision.model_validate(d) for d in payload["decisions"]]}
    if "baseline" in payload:
        systems["baseline"] = [Decision.model_validate(d) for d in payload["baseline"]]
    results = {name: score.score(ds, g) for name, ds in systems.items()}
    for name, (hits, extras) in results.items():
        _say(f"{name:>10}: {score.summarize(hits, extras)}")
    html = report.render(payload, systems, results)
    (out / "report.html").write_text(html)
    _say(f"wrote {out / 'report.html'}")


def main() -> None:
    p = argparse.ArgumentParser(prog="pii_demo")
    p.add_argument("-v", "--verbose", action="store_true", help="log cognition's decisions")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--out", type=Path, default=ROOT / "out")
        sp.add_argument("--gold", type=Path, default=ROOT / "corpus" / "gold.json")
        sp.add_argument("--policy", choices=["safe-harbor", "conservative"], default="safe-harbor")
        sp.add_argument("--min-confidence", type=float, default=0.6)

    c = sub.add_parser("check")
    c.add_argument("--model")
    c.add_argument("--base-url")
    r = sub.add_parser("run")
    r.add_argument("--model", help="model id or Pydantic AI model string (env PII_MODEL)")
    r.add_argument("--base-url", help='OpenAI-compatible endpoint (env PII_BASE_URL); "" for provider default')
    r.add_argument("--corpus", type=Path, default=ROOT / "corpus")
    r.add_argument("--trials", type=int, default=3, help="LLM votes per question (agreement = confidence)")
    r.add_argument("--timeout", type=int, default=180, help="seconds per LLM call")
    r.add_argument("--ref-year", type=int, default=date.today().year)
    r.add_argument("--no-baseline", action="store_true")
    common(r)
    d = sub.add_parser("redecide")
    d.add_argument("--save-as", type=Path, help="write to another folder instead of overwriting")
    common(d)
    rp = sub.add_parser("report")
    rp.add_argument("--out", type=Path, default=ROOT / "out")
    rp.add_argument("--gold", type=Path, default=ROOT / "corpus" / "gold.json")

    args = p.parse_args()
    if args.verbose:
        logging.basicConfig()
        logging.getLogger("cognition").setLevel(logging.INFO)
    {"check": cmd_check, "run": cmd_run, "redecide": cmd_redecide, "report": lambda a: _report(a.out, a.gold)}[
        args.cmd
    ](args)


if __name__ == "__main__":
    main()
