# Clipmaker Lite test — PROMOPAGES-9910

Self-contained test set for 20 PromoPages articles. Each article is mirrored
under the original contract paths in `PROMOPAGES-9857/` (all source images) and
`PROMOPAGES-9884/` (`content.json`). Only the first image block from each article
is generated in this run.

The 20 planning artifacts live under `artifacts/clipmaker-lite/v1/`; each one
contains one shared structured intent and independent plans for all three exact
model IDs. Provider prompts, run receipts, and MP4s live under `videos/`.

Use `manifest.json` as the review entry point. `dataset-manifest.json` records
the complete article/image inventory, and `generation-manifest.json` is the
resumable provider state. `visual-qa.md` records the frame-level visual review
separately from the machine media contract. `sandbox-resource.json` records the
published 60-file review bundle. The copied locked runner can re-check a
planning run:

```bash
python3 scripts/clipmaker_lite_runner.py provenance --run-id <run-id>
```
