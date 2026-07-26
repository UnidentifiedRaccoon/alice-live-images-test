# PROMOPAGES-9910 visual QA

Checked on 2026-07-24 after the final 20 x 3 batch was downloaded. This report
is independent of the machine media contract: `PASS`, `WARN`, and `FAIL` below
describe visible output quality and adherence to the planned action.

## Result

- 46 PASS
- 5 WARN
- 9 FAIL
- 60/60 MP4 files are readable.
- 40/60 pass the strict media contract: 20 `alibaba/wan-2.2` and 20
  `google/veo-3.1-lite`.
- All 20 `alibaba/wan-2.7` files are retained as raw generated outputs with
  `status: verification-failed`. The provider returned audio for all 20,
  non-1080 dimensions for 17, and a mismatched aspect ratio for 12.

## Per-article review

| Article | Wan 2.2 | Wan 2.7 | Veo 3.1 Lite |
| --- | --- | --- | --- |
| 01 | FAIL | PASS | WARN |
| 02 | WARN | PASS | PASS |
| 03 | PASS | PASS | PASS |
| 04 | FAIL | PASS | PASS |
| 05 | PASS | PASS | PASS |
| 06 | PASS | PASS | PASS |
| 07 | WARN | PASS | PASS |
| 08 | PASS | PASS | PASS |
| 09 | PASS | PASS | PASS |
| 10 | PASS | FAIL | PASS |
| 11 | PASS | PASS | PASS |
| 12 | PASS | PASS | PASS |
| 13 | PASS | PASS | PASS |
| 14 | FAIL | FAIL | FAIL |
| 15 | PASS | PASS | PASS |
| 16 | FAIL | PASS | PASS |
| 17 | FAIL | PASS | PASS |
| 18 | FAIL | PASS | WARN |
| 19 | PASS | PASS | PASS |
| 20 | WARN | PASS | PASS |

Model totals:

- `alibaba/wan-2.2`: 11 PASS / 3 WARN / 6 FAIL
- `alibaba/wan-2.7`: 18 PASS / 0 WARN / 2 FAIL
- `google/veo-3.1-lite`: 17 PASS / 2 WARN / 1 FAIL

## Failures

- `01 / alibaba/wan-2.2`: thick white ribbon-like artifacts cross the food and
  greenery through the middle of the clip.
- `04 / alibaba/wan-2.2`: an additional blink starts near the end, leaving the
  eye closed instead of returning to the required open terminal state.
- `10 / alibaba/wan-2.7`: the reflection becomes a large persistent glare that
  obscures the dashboard UI instead of clearing the display.
- `14 / all three models`: the earrings enlarge, detach, duplicate, or overlay
  the model portraits; the product geometry and collage layout are not
  preserved.
- `16 / alibaba/wan-2.2`: the handbag changes shape, detaches from the hand, and
  moves onto the stone support.
- `17 / alibaba/wan-2.2`: the light flare remains near the base of the buildings
  and never reaches the requested upper-floor terminal state.
- `18 / alibaba/wan-2.2`: an unrequested push-in accompanies strong mutation of
  prominent package copy.

## Warnings

- `02 / alibaba/wan-2.2`: the pain glow fades and the packages remain stable,
  but the body rotation and arm movement are stronger than planned.
- `07 / alibaba/wan-2.2`: clouds move continuously, but the sky and sun drift
  despite the fixed-camera instruction.
- `20 / alibaba/wan-2.2`: the phone lift overshoots into a selfie-like pose.
- `01 / google/veo-3.1-lite`: the foliage change is stronger than the requested
  light breeze, while the Mg card remains readable.
- `18 / google/veo-3.1-lite`: the mid-clip highlight is stronger than requested,
  while the products remain recognizable and stable.

## Method

Every selected output was checked at its first, middle, and final frame against
the source image and model-specific Lite prompt. Flagged clips were inspected
at nine evenly spaced frames. The review looked for visible corruption,
identity or product-geometry drift, text and UI damage, unintended cuts or
camera moves, frozen output, and failure to reach the planned terminal state.

Recommended visual retry set: nine outputs (`01/wan-2.2`, `04/wan-2.2`,
`10/wan-2.7`, all three article-14 outputs, `16/wan-2.2`, `17/wan-2.2`, and
`18/wan-2.2`). A retry requires a new external provider submission and is not
performed implicitly.
