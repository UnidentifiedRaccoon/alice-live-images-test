# Portrait angry outburst — visual review

## Intent

One continuous locked shot. The woman stays angry or frustrated throughout,
visibly yells, and shakes both already raised hands without a cut, reframing,
friendly smile, calming beat, or emotional reversal.

The emotional sign is the invariant; the face and body are expected to move
expressively. This corrects the earlier over-restrictive interpretation that
reduced the scene to a blink or static hold.

## Results

| Variant | Visual status | Review |
| --- | --- | --- |
| [Wan 2.2 — model-specific v1](wan-2.2/02.mp4) | PASS | Immediate readable scream, active raised hands, stable framing, and no happy reversal. The final frame remains clearly angry. |
| [Veo 3.1 Lite — model-specific v1](veo-3.1-lite/02.mp4) | PASS with minor deviation | Strong continuous angry performance and stable framing. The hands move inward toward the temples more than they oscillate side to side, but they remain raised and the emotional sign is preserved. |
| [Wan 2.7 — detailed v1](wan-2.7/02.mp4) | PARTIAL | Composition and tense expression remain stable, but the requested yell and hand shaking are too weak. |
| [Wan 2.7 — measured-amplitude v2](../portrait-angry-outburst-wan27-v2/wan-2.7/02.mp4) | FAIL | More mouth articulation, but hand shaking remains weak and several middle frames read as a smile-like expression. |
| [Wan 2.7 — short prompt + extension v3](../portrait-angry-outburst-wan27-extend-v3/wan-2.7/02.mp4) | PASS with choreography deviation | The strongest Wan 2.7 yell, clearly readable hand motion, stable framing, and no happy reversal. Instead of repeated side-to-side oscillation, the hands make one broader downward-and-outward shake. This is the preferred Wan 2.7 result. |

## Technical checks

- Wan 2.2: 1152×768, 97 frames, 30 fps, 3.233 s, no audio; request contract conforms.
- Wan 2.7 variants: 1764×1176, 90 frames, 30 fps, 3.0 s. The provider returned an AAC track despite `generate_audio: false`; raw outputs are preserved and the mismatch is recorded in each run artifact.
- Veo 3.1 Lite: 1920×1080, 96 frames, 24 fps, 4.0 s, no audio; request contract conforms.
- All variants use the original image only as `first_frame`; canonical model outputs were not overwritten.

## Prompting conclusion

Locking the emotional sign is compatible with expressive movement. The useful
constraint is `stays angry from first to final frame`, not `face and pose remain
unchanged`. Wan 2.2 and Veo responded well to an explicit sustained outburst.
Wan 2.7's detailed prompts preserved the frame more reliably than they followed
the requested hand oscillation. Extra kinematic detail increased mouth motion
without fixing the hands, while the short prompt with `prompt_extend: true`
finally produced a usable expressive outburst. Its tradeoff is lower
choreography precision: the provider chose one broader hand shake instead of
the specified repeated side-to-side path.
