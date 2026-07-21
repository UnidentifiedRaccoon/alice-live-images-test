# Google Veo 3.1 Lite

Checked: **2026-07-21**.

## Identity and clipmaker role

- OpenRouter model ID: `google/veo-3.1-lite`.
- Canonical OpenRouter version observed at check time: `google/veo-3.1-lite-20260331`.
- Current OpenRouter upstream route: Google Vertex, provider tag `google-vertex`.
- Direct Google model ID: `veo-3.1-lite-generate-001`.
- Intended use: single-image, first-frame image-to-video generation for a native **4-second** clip.

OpenRouter lists first- and last-frame inputs, but the clipmaker starts from one image and should send only `first_frame`. Google's direct API also documents video extension; that capability is not established by OpenRouter's normalized first-frame request and must not be promised by this route.

## Project target contract

| Field | Required baseline |
| --- | --- |
| Input | One public, directly downloadable HTTPS image as the first frame |
| Duration | `4 s` |
| Resolution | `720p` or `1080p`; choose explicitly |
| Aspect ratio | `16:9` or `9:16`; choose the source-compatible value |
| Audio | Choose explicitly with `generate_audio`; use `false` for a silent comparison |
| Last frame | Omitted for the single-image path |

OpenRouter currently exposes native durations of 4, 6, and 8 seconds. The clipmaker target is 4 seconds, not a longer request trimmed after generation.

## OpenRouter request form

Submit asynchronously with `POST /api/v1/videos`:

```json
{
  "model": "google/veo-3.1-lite",
  "prompt": "<English positive prompt>",
  "duration": 4,
  "resolution": "1080p",
  "aspect_ratio": "16:9",
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
      "google-vertex": {
        "parameters": {
          "negativePrompt": "<English undesired elements and qualities>"
        }
      }
    }
  }
}
```

The image URL must resolve directly for the provider without interactive authentication. Poll the returned job URL until completion or failure. OpenRouter does not publish a Veo-specific completion-time SLA.

`negativePrompt` is a confirmed allowed passthrough parameter on the current Google Vertex endpoint. It is camel-cased and belongs inside provider options; it is not a normalized top-level `negative_prompt` field.

## Prompt support and confirmed limits

- Positive prompt: supported; the clipmaker always supplies it for this route.
- Negative prompt: supported through `provider.options["google-vertex"].parameters.negativePrompt`.
- Confirmed positive text cap: **unknown**.
- Confirmed negative text cap: **unknown**.
- Endpoint metadata reports no `max_prompt_tokens`; this is absence of a declared cap, not proof that prompt length is unlimited.

Keep both prompts concise enough to remain testable. Do not invent a numeric character limit for either field.

For the negative prompt, follow Google's style: list undesired objects, artifacts, visual qualities, or motion outcomes as direct nouns and descriptive phrases. Avoid instruction-like wording built around `no`, `don't`, or `do not`.

```text
duplicate subject, extra limbs, warped hands, identity drift, camera shake,
abrupt cuts, added text overlays, invented logos, flicker, smeared motion
```

## Clipmaker guidance for 4 seconds

- Use a sharp, clear, well-composed source image. The source establishes subject, scene, composition, lighting, and visual style.
- In the positive prompt, focus on **motion**. Do not repeatedly redescribe the subject or background; use neutral references such as `the subject` when possible.
- Choose **one focused moment** that can finish inside four seconds. Avoid narratives of the form “first A, then B, then C.”
- Start the action immediately, place its main readable change near the middle, and leave the last part for a stable completed state.
- Prefer subtle, physically plausible subject motion. Add environmental motion only when it reinforces the same moment.
- For a subject that should remain still, pair `ACT_HOLD_AND_SETTLE` with at most one restrained camera move; do not combine zoom, pan, orbit, crane, and handheld behavior.
- Use a locked camera when subject motion is already the focus. Explicitly state smooth or stable camera behavior when unwanted shake would harm comparison.
- If audio is enabled, describe it in a separate short sentence. Keep visual motion instructions independent from dialogue, music, and ambient sound.

Keep the canonical priority from [pipeline.md](../pipeline.md); this model guidance changes
density and pacing, not composition order:

1. First-frame anchors.
2. One subject action and its stable completed state.
3. One camera instruction or `fixed camera`.
4. Supporting motion with visible evidence.
5. Brief realism and temporal-consistency terms.

## Direct Google constraints and route boundaries

Google's direct preview documentation for `veo-3.1-lite-generate-001` lists text-to-video, image-to-video, first-and-last-frame generation, prompt rewriting, and sound generation. It supports 4/6/8-second outputs, 720p/1080p, `16:9` and `9:16`, MP4 output, and 24 fps. It also documents source images up to 20 MB and English prompts for the preview model.

Those details describe the direct Google service. OpenRouter exposes a compatible subset through its normalized video API and provider passthrough. Direct-only features such as video extension, maximum output count, or future reference-image modes must be checked separately before use.

## Unknown or provider-specific

- Positive and negative prompt text limits: **unknown** for the current OpenRouter route.
- Runtime and queue behavior: asynchronous and **not covered by a published SLA** here.
- Google's 24 fps, preview status, input-size rules, and direct video-extension behavior are direct-service constraints; verify what survives the OpenRouter adapter.
- `negativePrompt`, `personGeneration`, `conditioningScale`, and `enhancePrompt` are provider passthrough parameters whose availability can change. Re-read endpoint metadata before a paid request.
- Audio generation can materially change prompt behavior and output; always set `generate_audio` deliberately.

## Sources

- [OpenRouter Veo 3.1 Lite model page](https://openrouter.ai/google/veo-3.1-lite)
- [OpenRouter Veo 3.1 Lite endpoint metadata](https://openrouter.ai/api/v1/models/google/veo-3.1-lite/endpoints)
- [OpenRouter video model registry](https://openrouter.ai/api/v1/videos/models)
- [OpenRouter submit-video API](https://openrouter.ai/docs/api/api-reference/video-generation/submit-a-video-generation-request)
- [OpenRouter image-to-video cookbook](https://openrouter.ai/docs/cookbook/video-generation/image-to-video)
- [OpenRouter provider-specific video options](https://openrouter.ai/docs/cookbook/video-generation/provider-specific-video-options)
- [Google Veo 3.1 model documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate?hl=en)
- [Google video generation best practices](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice?hl=en)
- [Google video generation prompt guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide?hl=en)
