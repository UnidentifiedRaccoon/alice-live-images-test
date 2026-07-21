# Alibaba Wan 2.7

Checked: **2026-07-21**.

## Identity and clipmaker role

- OpenRouter model ID: `alibaba/wan-2.7`.
- Canonical OpenRouter version observed at check time: `alibaba/wan-2.7-20260414`.
- Current OpenRouter upstream route: AtlasCloud, provider tag `atlas-cloud`.
- Intended use: single-image, first-frame image-to-video generation for a **5-second** clip.

The model also supports text-to-video and first-and-last-frame generation, but the clipmaker starts from one image and should send it as `first_frame`.

## Project target contract

| Field | Baseline value |
| --- | --- |
| Input | One public, directly downloadable HTTPS image as the first frame |
| Duration | `5 s` |
| Resolution | `1080p` in the tracked comparison; OpenRouter also lists `720p` |
| Aspect ratio | Request the source-compatible supported ratio; the tracked comparison requested `16:9` |
| Seed | Explicit when repeatability matters; tracked comparison used `9681` |
| Audio | Explicitly choose with `generate_audio`; use `false` for a silent comparison result |
| Last frame | Omitted for the clipmaker's single-image path |

Current OpenRouter metadata lists integer durations from 2 through 10 seconds, 720p/1080p output, aspect ratios `16:9`, `9:16`, `1:1`, `4:3`, and `3:4`, and both first- and last-frame images.

## OpenRouter request form

Submit asynchronously with `POST /api/v1/videos`:

```json
{
  "model": "alibaba/wan-2.7",
  "prompt": "<English positive prompt>",
  "duration": 5,
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
          "negative_prompt": "<English negative prompt, at most 500 characters>"
        }
      }
    }
  }
}
```

The image must be reachable by the provider without browser authentication or an HTML landing page. The response is a job; follow its `polling_url` until completion or failure. OpenRouter does not publish a per-model completion-time SLA.

`negative_prompt` is currently listed as an allowed passthrough parameter for the AtlasCloud endpoint. Provider-option schemas can change, so re-read endpoint metadata before sending a paid request. The `atlas-cloud` nesting above follows the current provider tag and OpenRouter provider-options convention.

## Prompt support and confirmed limits

- Positive prompt: supported; the clipmaker always supplies it for this route.
- Positive prompt maximum on the current OpenRouter/AtlasCloud route: **unknown**. Endpoint metadata reports no `max_prompt_tokens`; that does not mean unlimited text.
- Negative prompt: supported through AtlasCloud provider options.
- Negative prompt maximum for the project's current AtlasCloud route: **500 characters**. Enforce `<= 500` before submission and retain a small safety margin if the provider's character-counting semantics are uncertain.

The 500-character AtlasCloud constraint is corroborated by the tracked project evidence: two longer negative prompts, 716 and 622 characters, were deliberately not sent because they exceeded the route limit. See [model-comparison-5s/comparison-data.js](../../../../model-comparison-5s/comparison-data.js).

Alibaba's **direct** Wan 2.7 API is a different provider contract. Its documented positive prompt maximum is 5000 characters and negative prompt maximum is 500 characters, with 2–15-second generation. Do not infer the 5000-character positive allowance for OpenRouter/AtlasCloud; OpenRouter currently exposes only 2–10 seconds for this route.

## Clipmaker guidance for 5 seconds

- Use the source image as the visual specification. In I2V, prompt primarily for motion and camera behavior instead of redescribing appearance.
- Build the clip around **one continuous shot and one completed action**. Five seconds allow a little preparation and settling, not a chain of unrelated actions.
- Start motion promptly, make the main beat readable before the final second, and reserve the ending for a natural settle or held result.
- State direction, speed, and amplitude for the subject motion. Prefer small-to-moderate motion that can finish cleanly in five seconds.
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

OpenRouter jobs are asynchronous. The tracked AtlasCloud comparison completed two 5-second generations in approximately 95 and 126 seconds. These are observations, not an SLA.

The same evidence shows why output validation is mandatory: requests specified `16:9`, 1080p, and no final audio, while raw results followed source-like geometries and contained an AAC track that the comparison pipeline removed during remux. Verify actual dimensions, duration, frame rate, and audio instead of trusting request metadata alone.

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
