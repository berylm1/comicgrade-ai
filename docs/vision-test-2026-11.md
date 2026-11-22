# Vision test for the scan flow (weekend of Nov 14-15, 2026)

Status: **harness ready, no approach measured yet.** Nothing in this file is a model result.

## Why nothing was measured here

The work ran in a cloud container that could not run any of the candidates:

| Candidate | Blocker in the container |
|---|---|
| Claude vision (cloud) | No Anthropic API key in the container |
| OpenAI vision (already wired) | api.openai.com blocked by the container's network rules; no key |
| CLIP retrieval vs GCD covers | huggingface.co (model weights) and comics.org (covers) blocked; the Milestone 1 pipeline lives on the Mac |
| ML Kit OCR + fuzzy match | Runs on a phone only |

Ten of the eleven photos were supplied (07, Fantastic Four #126, was not). Per the rules, no keys or vendor sign-ups were requested and no covers were fetched.

## What was built

`backend/eval/`, runnable on the Mac where the keys, network and photos are:

- `ground_truth.json`: the 11 photos from the brief, with the traps and targets.
- `bench.py run`: calls Claude (or the app's existing OpenAI provider) once per photo, one at a time, and records the top three answers, latency, tokens and cost.
- `bench.py score`: scores a results file from **any** approach. The CLIP pipeline and the phone's ML Kit test write the same JSON format (documented at the top of `bench.py`), so all candidates are scored by one scorer.
- The report gives the per-photo table, top-1/top-3 against the 80%/95% bar, series/issue/variant accuracy, each trap, and cost and latency per scan, with a flag above $0.10.

Scoring rules, as the brief sets them:

- A candidate is right when series, issue number and format all match. Format separates the Annual (08) and the Deluxe Edition (06) from single issues.
- Variant is scored only on 09, the one cover that names itself a variant. No variant artists.
- Any printing claim makes that answer wrong.
- Years are reported but not scored.
- Missing photos are listed, not counted as wrong; errors and refusals count as wrong.
- 01 vs 03 passes when both read as Action Comics #1000. Whether the two arts stay apart is a catalog-matching question that CLIP already measured (0.8092), so a single-photo reader can't fail it.

`backend/tests/test_eval.py` covers the scoring rules and a full run with the SDK mocked.

## How to run it (Mac)

```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # from your shell or keychain, never committed
python -m eval.bench run --approach claude --effort medium --photos ~/workspace/goals/comicgrade-ai/test-photos
python -m eval.bench run --approach claude --effort low    --photos ~/workspace/goals/comicgrade-ai/test-photos
python -m eval.bench score eval/results/<clip-or-mlkit-results>.json
```

Each Claude run is 11 billed API calls. Reports land in `backend/eval/results/`; commit them so Muse can review.

## Candidate list for the weekend (three, tested properly)

1. **On-device ML Kit OCR + fuzzy series match.** This is the shipped direction and the bar to beat. On-device and free per scan. Run it on the phone and export results in the bench format.
2. **CLIP retrieval against GCD covers.** Already prototyped in Milestone 1 and on-device-capable. This test adds top-1/top-3 on the full set; the margin numbers already measured stand.
3. **Claude vision.** Already wired in the app as `VISION_PROVIDER=claude`. It's a cloud call, so cost and latency per scan are the open questions, at effort `low` and `medium`.

Left out:
- **OpenAI vision:** the harness supports it, but the app's call returns only one answer and drops token usage, so it can't report top-3 or cost without changes.
- **A local open VLM:** a different on-device project from what the scan flow needs this month.

The bench prompt (`eval/providers.py`) encodes the spec's rules: annual vs monthly, collected editions, variants only when named, no printing calls. The app's grading prompt does not have these rules yet. If Claude is chosen, the app should adopt this prompt and return the top three answers.

## Findings about the test set itself

- **09 ground truth year looks wrong.** The cover has the large "U" Ultimate logo, the VARIANT EDITION box, and the new costume. Those match the **2024** Ultimate Spider-Man #1, not the 2000 series. The year isn't scored, but if 2000 is used as the GCD year gate, the right issue gets filtered out. Please confirm against GCD before Muse uses it.
- **Most images are clean scans, not phone photos.** Eight of the ten supplied images are flat digital scans or product shots: no glare, perspective or bag. The exceptions are 04 (a photo with wide borders, 400x400) and the very small 01 (255x391 pixels). Scores on this set will be optimistic for the real scan flow, except where resolution hurts. Add phone photos of physical books before deciding.
- 07 (Fantastic Four #126) was not supplied, so the set here is 10 photos and 9 distinct issues.
