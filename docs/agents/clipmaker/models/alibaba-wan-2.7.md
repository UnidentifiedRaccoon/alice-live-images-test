# Alibaba Wan 2.7

Checked: **2026-07-21**.

## Identity and clipmaker role

- OpenRouter model ID: `alibaba/wan-2.7`.
- Canonical OpenRouter version observed at check time: `alibaba/wan-2.7-20260414`.
- Current OpenRouter upstream route: AtlasCloud, provider tag `atlas-cloud`.
- Intended use: single-image image-to-video generation for a native
  **3-second** comparison clip. Longer native durations are supported, but the
  tracked 5-second runs visibly stretched several micro-actions.
- Controlled prompt replay may use another supported native duration when the
  user requires it. The tracked portrait replay uses native `5 s`; it is not
  trimmed or retimed and does not change the 3-second calibrated default.

The model also supports text-to-video and first-and-last-frame generation. The
clipmaker always sends the source as `first_frame`; it may reuse the same source
as `last_frame` only when the completed state must exactly return to it.

## Project target contract

| Field | Baseline value |
| --- | --- |
| Input | One public, directly downloadable HTTPS image as the first frame |
| Duration | `3 s` for the calibrated comparison |
| Resolution | `1080p` in the tracked comparison; OpenRouter also lists `720p` |
| Aspect ratio | Request the source-compatible supported ratio; the tracked comparison requested `16:9` |
| Seed | Explicit when repeatability matters; tracked comparison used `9681` |
| Audio | Explicitly choose with `generate_audio`; use `false` for a silent comparison result |
| Last frame | Normally omitted; reuse the source only for an exact return-to-source state |

Current OpenRouter metadata lists integer durations from 2 through 10 seconds, 720p/1080p output, aspect ratios `16:9`, `9:16`, `1:1`, `4:3`, and `3:4`, and both first- and last-frame images.

## OpenRouter request form

Submit asynchronously with `POST /api/v1/videos`:

```json
{
  "model": "alibaba/wan-2.7",
  "prompt": "<English positive prompt>",
  "duration": 3,
  "resolution": "1080p",
  "aspect_ratio": "16:9",
  "seed": 9681,
  "generate_audio": false,
  "frame_images": [
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.invalid/source-image.jpg"
      },
      "frame_type": "first_frame"
    }
  ],
  "provider": {
    "options": {
      "atlas-cloud": {
        "parameters": {
          "negative_prompt": "<English negative prompt, at most 500 characters>",
          "prompt_extend": false
        }
      }
    }
  }
}
```

The image must be reachable by the provider without browser authentication or
an HTML landing page. The response is a job; follow its `polling_url` until
completion or failure. OpenRouter does not publish a per-model completion-time
SLA. For an exact return-to-source state, add the same source URL as a second
`frame_images` item with `frame_type: "last_frame"`. Do not add it when the
completed state is spatially different from the source.

`negative_prompt` and `prompt_extend` are currently listed as allowed passthrough
parameters for the AtlasCloud endpoint. Keep `prompt_extend: false` for the
controlled comparison: the clipmaker prompt already contains an exact motion
plan and provider rewriting would add an uncontrolled variable. This flag does
not control speed. Provider-option schemas can change, so re-read endpoint
metadata before sending a paid request. The `atlas-cloud` nesting above follows
the current provider tag and OpenRouter provider-options convention.

For an explicit cross-model replay of the Wan 2.2 demo request, preserve the
demo's actual single-string transport: send the copied Positive followed by
`\n\nAvoid: ` and the copied Negative as the top-level `prompt`, and omit the
separate AtlasCloud `negative_prompt`. Mark this exceptional request with
`prompt_source_model_id` and `embed_negative_in_positive`. Do not use this
transport as the default Wan 2.7 authoring format.

## Prompt support and confirmed limits

- Positive prompt: supported; the clipmaker always supplies it for this route.
- Positive prompt maximum on the current OpenRouter/AtlasCloud route: **unknown**. Endpoint metadata reports no `max_prompt_tokens`; that does not mean unlimited text.
- Negative prompt: supported through AtlasCloud provider options.
- Negative prompt maximum for the project's current AtlasCloud route: **500 characters**. Enforce `<= 500` before submission and retain a small safety margin if the provider's character-counting semantics are uncertain.

The 500-character AtlasCloud constraint is corroborated by the tracked project evidence: two longer negative prompts, 716 and 622 characters, were deliberately not sent because they exceeded the route limit. See [model-comparison-5s/comparison-data.js](../../../../model-comparison-5s/comparison-data.js).

Alibaba's **direct** Wan 2.7 API is a different provider contract. Its documented positive prompt maximum is 5000 characters and negative prompt maximum is 500 characters, with 2–15-second generation. Do not infer the 5000-character positive allowance for OpenRouter/AtlasCloud; OpenRouter currently exposes only 2–10 seconds for this route.

## Clipmaker guidance for 3 seconds

- Use the source image as the visual specification. In I2V, prompt primarily for motion and camera behavior instead of redescribing appearance.
- Build the clip around **one continuous shot and one completed action**. Three seconds allow one short beat and a brief hold, not a chain of actions.
- Start motion immediately at normal real-time speed. Complete a familiar micro-action by about `1.8 s`; use the remaining time for a stable hold instead of stretching the action across the clip.
- State direction, speed, amplitude and the physical completion condition. Prefer small-to-moderate motion with a visible contact, recoil, weight transfer or other causal result.
- Do not use `slowly`, `barely perceptible`, `very small settle`, repeated `calm/steady` phrasing or prolonged easing for a dynamic scene unless slow motion is explicitly requested. Add `slow motion, time-stretched motion, delayed action` to the negative prompt when relevant.
- Default to `fixed camera` or a locked camera. If motion is justified, choose one restrained move such as a slow push-in, slight pan, or gentle lateral drift.
- Avoid rapid scene changes, long action sequences, cuts, and contradictory camera instructions. To suppress multi-shot behavior, include `Generate a single-shot video.` when needed.
- Keep environmental motion secondary and causally consistent with the main action.
- If audio is generated, write audio intent as a separate concise sentence. If `generate_audio` is `false`, do not spend prompt budget on a soundtrack.

Keep the canonical priority from [pipeline.md](../pipeline.md); this model guidance changes
density and pacing, not composition order:

1. First-frame anchors.
2. One subject action and its stable completed state.
3. One camera instruction or `fixed camera`.
4. Supporting motion with visible evidence.
5. Brief realism and temporal-consistency terms.

## Runtime and observed behavior

OpenRouter jobs are asynchronous. The tracked AtlasCloud runs completed on an
order-of-minutes timescale. This is an observation, not an SLA.

Neither the normalized OpenRouter request nor the current AtlasCloud
passthrough schema exposes a `speed`, `fps` or `slow_motion` parameter. Output
frame rate is not an action-speed control. Control perceived tempo through the
positive motion wording, an early absolute completion time, a supported native
duration and slow-motion negative fragments; never invent a runtime speed
field. In the tracked cat A/B, reducing the request from 5 to 3 seconds moved
paw contact from roughly 3.0 to 1.5 seconds. It did not fix every scene by
itself, so validate the actual action timing from frames.

The same evidence shows why output validation is mandatory: requests specified
1080p and no audio, while raw results followed source-like geometries and
contained an AAC track. The comparison pipeline preserves that raw output and
records the mismatch. Verify actual dimensions, duration, frame rate and audio
instead of trusting request metadata alone.

The tracked angry-portrait A/B is a second calibration boundary. A long
preservation-heavy prompt kept the expression stable but largely suppressed
the requested hand shaking. Adding an exact oscillation count and travel
amplitude increased mouth motion without reliably increasing hand motion and
introduced smile-like intermediate shapes. A short prompt with
`prompt_extend: true` produced the strongest yell and clearly readable hand
motion while preserving the angry emotional sign, but the provider replaced
the requested repeated side-to-side oscillation with one broader
downward-and-outward shake. Provider rewriting is therefore a useful energy
lever and an explicit choreography confounder. Do not equate emotional
continuity with a static face, and do not keep lengthening the prompt when one
articulated body-part motion is repeatedly ignored; choose between strict
choreography and model improvisation deliberately.

## Unknown or provider-specific

- OpenRouter/AtlasCloud positive prompt cap: **unknown**.
- Exact server-side character-counting rules for the 500-character negative prompt: **unknown**; validate locally before submission.
- Direct Alibaba limits, 2–15-second duration, media variants, and typical 1–5-minute generation time are provider-specific and do not override OpenRouter metadata.
- `prompt_extend`, audio behavior, and optional last-frame handling are passthrough/provider behaviors; keep them explicit and revalidate endpoint metadata.
- Pricing, queue time, and output conformance can change independently of this specification.

## Sources

- [OpenRouter Wan 2.7 model page](https://openrouter.ai/alibaba/wan-2.7)
- [OpenRouter Wan 2.7 endpoint metadata](https://openrouter.ai/api/v1/models/alibaba/wan-2.7/endpoints)
- [OpenRouter video model registry](https://openrouter.ai/api/v1/videos/models)
- [OpenRouter submit-video API](https://openrouter.ai/docs/api/api-reference/video-generation/submit-a-video-generation-request)
- [OpenRouter image-to-video cookbook](https://openrouter.ai/docs/cookbook/video-generation/image-to-video)
- [OpenRouter provider-specific video options](https://openrouter.ai/docs/cookbook/video-generation/provider-specific-video-options)
- [Alibaba general image-to-video API](https://www.alibabacloud.com/help/en/model-studio/image-to-video-general-api-reference)
- [Alibaba text-to-video prompt guide](https://www.alibabacloud.com/help/en/model-studio/text-to-video-prompt)
- [Tracked project comparison evidence](../../../../model-comparison-5s/comparison-data.js)
