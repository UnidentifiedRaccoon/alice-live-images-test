# Clipmaker Lite 5×3 rerun — 2026-07-23

Batch ID: `promopages-9891-lite3-20260723`.

## Prompt provenance

- 15 prompts were authored only by the isolated `clipmaker-lite` runner.
- Every image/model pair used a separate singleton run.
- Provenance is `verified: true` for all 15 results under contract `1.2.1`.
- No prompt was copied between models. Baseline `negative_prompt` is absent for all 15 runs.
- The generation bridge revalidates Lite provenance immediately before every provider operation.

## Generation result

All 15 provider jobs completed and produced decodable MP4 files. The canonical
machine-readable report is [manifest.json](manifest.json).

| Model route | Files | Runtime contract |
| --- | ---: | ---: |
| `alibaba/wan-2.2` → `wan-streamlit` | 5/5 | 5/5 conforming |
| `alibaba/wan-2.7` → Eliza/OpenRouter → `atlas-cloud` | 5/5 | 0/5 strictly conforming |
| `google/veo-3.1-lite` → Eliza/OpenRouter → `google-vertex` | 5/5 | 5/5 conforming |

Wan 2.2 outputs contain 97 frames at 30 fps, last 3.233 seconds, preserve the
source aspect ratio within tolerance, and have no audio. Veo outputs are
1920×1080, last 4 seconds, and have no audio.

Atlas Cloud returned a 5-second Wan 2.7 file for every input, but ignored
`generate_audio: false` in all five cases. It also preserved the source aspect
ratio instead of the selected supported ratio in four cases and consequently
returned nonstandard dimensions. These are retained as raw provider results;
the bridge does not conceal the deviations through post-processing.

## Visual smoke check

All 15 MP4 files decode from beginning to end, and midpoint frames are nonblank
and related to their source images. The generated motion is visible in the
product drop, cat step, pool ripples, portrait expression, and finance UI cases.

Notable content-level observations from midpoint frames:

- the Wan 2.2 portrait changes the hand pose and facial expression more strongly
  than requested;
- the Wan 2.2 finance UI invents short chart text;
- all three UI variants alter fine text to some degree, which remains a fragile
  case for image-to-video generation.

These observations are quality notes, not provenance or transport failures.
