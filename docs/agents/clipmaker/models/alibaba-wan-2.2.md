# Alibaba Wan 2.2

Checked: **2026-07-21**.

## Identity and clipmaker role

- Project model identifier: `alibaba/wan-2.2`.
- Intended use: legacy single-image, first-frame image-to-video generation for the short clipmaker contract.
- OpenRouter status: `alibaba/wan-2.2` is **absent** from the current video-model registry. Its endpoint metadata also cannot be resolved. Do not submit a paid OpenRouter request with this ID until it appears in the registry and its endpoint metadata has been checked again.
- The exact current OpenRouter request parameters, provider route, prompt limits, and runtime are therefore **unverified**.

This project contract is not the same thing as Alibaba's current direct Wan 2.2 APIs. Keep them separate in implementation and documentation.

## Project target contract

The existing clipmaker path must preserve this local runtime contract:

| Field | Required value |
| --- | --- |
| Input | One source image used as the first frame |
| Clipmaker target duration | `3.2 s` |
| Legacy adapter runtime | `97 / 30 = 3.233… s` (about `3.23 s`) |
| Frames | `97` |
| Frame rate | `30 fps` |
| Resolution tier | `720p` |
| Aspect ratio | Preserve the source aspect ratio |
| Last frame | Not supplied |
| Looping | Disabled |

The 97-frame contract belongs to the project's legacy runtime adapter. It is **not** a confirmed OpenRouter capability and is **not** a supported duration of Alibaba's direct hosted Wan 2.2 endpoints.

## Input and request form

Until OpenRouter lists the model, treat this as an internal adapter contract rather than an OpenRouter payload:

```yaml
model: alibaba/wan-2.2
input:
  first_frame_url: https://example.invalid/source-image.jpg
  positive_prompt: <English motion prompt>
  negative_prompt: <English exclusions prompt>
runtime:
  frames: 97
  fps: 30
  duration_seconds: 3.2333333333
  resolution: 720p
  aspect_ratio: source
  loop: false
```

The image URL shown above is illustrative. The runtime adapter must use an accessible image or its own supported upload mechanism. Do not translate this YAML mechanically into `POST /api/v1/videos`: there is no verified OpenRouter endpoint for the model.

Alibaba's **direct** hosted APIs expose separate model IDs and a different request contract:

| Direct Alibaba model ID | Purpose | Hosted duration / tier |
| --- | --- | --- |
| `wan2.2-i2v-flash` | First-frame I2V | Fixed 5 s; 480p or 720p; silent |
| `wan2.2-i2v-plus` | First-frame I2V | Fixed 5 s; 480p or 1080p; silent |
| `wan2.2-kf2v-flash` | First-and-last-frame I2V | Fixed 5 s; 480p, 720p, or 1080p; silent |
| `wan2.2-t2v-plus` | Text-to-video, not the clipmaker's single-image path | Fixed 5 s; 480p or 1080p |

A representative direct Alibaba first-frame request uses the provider's asynchronous video-synthesis endpoint and this provider-specific shape:

```json
{
  "model": "wan2.2-i2v-flash",
  "input": {
    "img_url": "https://example.invalid/source-image.jpg",
    "prompt": "<positive prompt>",
    "negative_prompt": "<negative prompt>"
  },
  "parameters": {
    "resolution": "720P",
    "prompt_extend": true,
    "watermark": false,
    "seed": 9681
  }
}
```

That request produces a provider-native 5-second result. It does not satisfy the local 97-frame contract without an explicit downstream timing conversion, which must not be assumed to be lossless.

Direct Alibaba input constraints are provider-specific: JPEG/JPG/PNG images, no alpha channel, dimensions from 240 to 8000 pixels, and a file size up to 10 MB. Confirm the current endpoint documentation before a paid call.

## Prompt support and confirmed limits

The clipmaker must continue returning both an English positive prompt and an English negative prompt. For the project's legacy adapter, enforcement limits are **unknown** because the current provider route is not documented here.

For the direct Alibaba Wan 2.2 endpoints only:

- Positive prompt: up to **800 characters**.
- Negative prompt: up to **500 characters**; longer text may be truncated by the provider.
- `prompt_extend`: supported, with `true` as the documented default.
- `seed`: supported in the range `0` to `2147483647`.

Do not apply those direct-API limits to an unidentified legacy or future OpenRouter route without revalidation.

## Clipmaker guidance for the 3.2-second target

- Start from what is visibly present in the source image; do not redesign the subject, scene, composition, lighting, or style.
- Describe **one small, continuous, completed action**. A 3.2-second target cannot carry a sequence of independent beats.
- Start the motion immediately. Put the main readable beat in the first half or middle, then let movement settle in the final frames.
- Prefer a locked camera. Add only one minimal camera behavior when the image gives it a clear spatial reason; never stack pan, zoom, orbit, and handheld motion.
- Name motion direction, speed, and amplitude when ambiguity would cause a wrong result.
- Keep background motion subordinate to the main action. Avoid cuts, scene changes, entrances of new subjects, transformations, and loops.
- The prompt should describe the intended motion, not runtime settings such as frame count or codec.

## Unknown or provider-specific

- OpenRouter availability, upstream provider, normalized fields, provider options, positive/negative limits, billing, and runtime: **unknown** for `alibaba/wan-2.2` as of the checked date.
- The project's 97 frames at 30 fps and 720p are a local legacy contract, not current public-provider metadata.
- Alibaba direct endpoints are asynchronous and commonly take minutes depending on queue and load; this is not an SLA for the project route.
- The open-source Wan 2.2 repository has its own checkpoints and inference settings. Those do not establish an OpenRouter contract.

## Sources

- [OpenRouter video model registry](https://openrouter.ai/api/v1/videos/models)
- [OpenRouter endpoint lookup for the project ID](https://openrouter.ai/api/v1/models/alibaba/wan-2.2/endpoints)
- [Wan 2.2 open-source repository](https://github.com/Wan-Video/Wan2.2)
- [Alibaba legacy first-frame image-to-video API](https://www.alibabacloud.com/help/en/model-studio/legacy-image-to-video-api-reference/)
- [Alibaba legacy first-and-last-frame image-to-video API](https://www.alibabacloud.com/help/en/model-studio/legacy-image-to-video-by-first-and-last-frame-api-reference)
- [Alibaba text-to-video API](https://www.alibabacloud.com/help/en/model-studio/text-to-video-api-reference)
