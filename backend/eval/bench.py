"""Vision identification benchmark for the scan flow.

Run an approach over the test photos, then score it:

    cd backend
    python -m eval.bench run --approach claude --photos ~/workspace/goals/comicgrade-ai/test-photos
    python -m eval.bench run --approach claude --effort low --photos ...
    python -m eval.bench run --approach openai --photos ...
    python -m eval.bench score eval/results/clip-retrieval.json     # results from another pipeline

`run` calls the API once per photo, one at a time (so latency is per scan),
and writes <out>/<date>-<approach>-<effort>.json plus a .md report.
`claude` needs ANTHROPIC_API_KEY; `openai` needs OPENAI_API_KEY. Each run is
billed: 11 photos is 11 API calls.

Results format (for CLIP, ML Kit or anything else scored with `score`):
{
  "meta": {"approach": "...", "model": "...", "runs_on": "on-device | cloud", "run_at": "..."},
  "photos": [
    {"id": "01", "candidates": [{"series": "...", "issue_number": "...", "format": "single_issue",
      "variant_named_on_cover": false, "printing": null, "cover_year": 2018}],
     "latency_s": 1.2, "cost_usd": 0.0, "error": null}
  ]
}
Photos left out are reported as missing, not wrong.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import providers
from .score import load_truth, render, score

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def find_photo(folder: Path, photo_id: str) -> Path | None:
    """Match by the NN- prefix with any image extension (10 may be .png)."""
    for path in sorted(folder.iterdir()):
        if path.name.startswith(f"{photo_id}-") and path.suffix.lower() in IMAGE_EXTS:
            return path
    return None


async def run(approach: str, photos: Path, model: str, effort: str, client=None) -> dict:
    truth = load_truth()
    if approach == "claude" and client is None:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic()
    rows = []
    for t in truth["photos"]:
        path = find_photo(photos, t["id"])
        if path is None:
            rows.append({"id": t["id"], "status": "missing"})
            print(f"{t['id']}: missing", file=sys.stderr)
            continue
        data, media = path.read_bytes(), providers.media_type_for(path)
        if approach == "claude":
            out = await providers.run_claude(client, data, media, model, effort)
        elif approach == "openai":
            out = await providers.run_openai(data, media)
        else:
            raise SystemExit(f"unknown approach {approach!r}")
        rows.append({"id": t["id"], "file": path.name, **out.__dict__})
        top = out.candidates[0] if out.candidates else None
        print(f"{t['id']}: {top and (top.get('series'), top.get('issue_number'))} {out.error or ''}", file=sys.stderr)
    return {
        "meta": {
            "approach": approach,
            "model": model if approach == "claude" else "app OpenAI provider (OPENAI_VISION_MODEL)",
            "effort": effort if approach == "claude" else None,
            "runs_on": "cloud",
            "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "photos": rows,
    }


def write(results: dict, out: Path, stem: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stem}.json").write_text(json.dumps(results, indent=1))
    report = out / f"{stem}.md"
    report.write_text(render(results, score(results)))
    return report


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run an approach over the photos and score it")
    r.add_argument("--approach", choices=["claude", "openai"], required=True)
    r.add_argument("--photos", type=Path, required=True)
    r.add_argument("--model", default="claude-opus-5-5")
    r.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    r.add_argument("--out", type=Path, default=Path(__file__).with_name("results"))
    s = sub.add_parser("score", help="score a results file from any approach")
    s.add_argument("results", type=Path)
    args = parser.parse_args(argv)

    if args.cmd == "run":
        if not args.photos.is_dir():
            raise SystemExit(f"{args.photos} is not a folder")
        results = asyncio.run(run(args.approach, args.photos, args.model, args.effort))
        stamp = datetime.now().strftime("%Y-%m-%d")
        stem = f"{stamp}-{args.approach}" + (f"-{args.model}-{args.effort}" if args.approach == "claude" else "")
        print(write(results, args.out, stem))
    else:
        results = json.loads(args.results.read_text())
        print(write(results, args.results.parent, args.results.stem))


if __name__ == "__main__":
    main()
