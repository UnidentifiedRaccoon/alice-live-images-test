# Step 8 — Clipmaker Lite Tune

## Scope

Source: [PROMOPAGES-10060 video evaluation](https://docs.google.com/spreadsheets/d/18yfX_hV3h1JnQsdj67JPubievxs2xpjW4_NcfluaZ-E/edit?gid=1657768450#gid=1657768450), tab `Оценка`, rows 2–316.

The Tune set uses column `M` as the decision field and includes every row where it is blank or equals `Перегенерация (-)`. Columns `N` and `O` are empty and are not treated as decisions.

- 65 target model rows across 36 source images and 18 articles;
- 38 explicit regenerations and 27 blank decisions;
- 62 of 65 targets have reviewer feedback in column `P`;
- Veo 3.1 Lite: 25 targets; Wan 2.2: 24; Wan 2.7: 16;
- 27 of 36 images have a non-target sibling model, but those siblings are relative counterexamples rather than gold labels.

## Failure pattern

| Primary failure | Rows | Share |
| --- | ---: | ---: |
| Wrong or implausible action / physics | 25 | 38.5% |
| Source, identity, text or graphic continuity | 20 | 30.8% |
| Camera, shot or tempo artifact | 7 | 10.8% |
| Insufficient visible motion | 6 | 9.2% |
| Optical accent failure | 4 | 6.2% |
| No reviewer comment | 3 | 4.6% |

The two dominant classes account for 69.2% of targets. The recurring problem is not prompt length. It is an unsafe choice of what is allowed to move and what evidence from the first frame must remain invariant.

Key observations:

1. Preservation prose alone does not protect UI, charts or readable text. In case `14#04`, all three models changed the screenshot despite explicit text/layout preservation. These scenes need a deterministic compositor gate.
2. The planner sometimes ignored that the requested endpoint was already visible. In `03#09` the arrow already points at 3.9; in `07#03` the person is already at the top of the exercise. Replaying a full action creates reversal or an invented cycle.
3. Generic semantic preservation is too weak for people, rides and tools. Entity count, rigid attachment, contact topology, motion owner and causal direction must be explicit invariants.
4. Complex articulated rides, face-adjacent hands, deformable objects and unsupported tool mechanics are high-risk actions. A bounded camera move is safer when the exact action cannot be inferred from the image.
5. Model amplitude is asymmetric: Wan 2.2 needs a perceptual motion floor for otherwise static micro-motion; Wan 2.7 needs stronger travel/effect containment; Veo with prompt enhancement needs explicit identity and architecture anchors.
6. A fixed-camera instruction is insufficient after observed cuts or jitter. The prompt needs one continuous shot, one bounded camera path and an observable end displacement.

## Clipmaker Lite 2.2.0 changes

The updated contract adds an image-grounded feasibility gate before model prompting and expands the scene intent to ten required fields:

- exact editorial meaning and bound article/image locator;
- initial and terminal state;
- motion owner and one primary action;
- geometry, identity and semantic invariants;
- feasibility assessment;
- one scene-level rendering strategy: `image-to-video`, `camera-only` or `deterministic-compositor`.

Additional safeguards:

- if the terminal state is already visible, the planner must use residual motion or a camera move instead of reversing or replaying the action;
- readable text, UI, charts and diagrams default to deterministic composition when no source-grounded nonsemantic generative motion is safe;
- entity cardinality, passive anchors, rigid attachments, contact surfaces and causal direction are preserved explicitly;
- one primary motion hierarchy prevents fabric, particles or background vegetation from taking over a camera-led shot;
- architecture is camera-led; local vegetation may move only in place;
- model-specific visibility floors and upper bounds are encoded in the three model specifications;
- `negative_prompt` remains machine-owned `null`;
- compositor plans carry `positive_prompt: null` and fail closed before any video transport;
- the author sees the exact article image locator instead of only the full article JSON.

Historical Lite 2.0.6–2.0.8 verification remains reproducible through a frozen support snapshot.

## Tune result

All 36 planning runs were prepared and authored by the isolated Clipmaker Lite runner. Every result re-verifies against contract `2.2.0` with runner version `9`.

| Scene strategy | Source images | Target model rows |
| --- | ---: | ---: |
| Deterministic compositor | 11 | 22 |
| Camera-only I2V | 21 | 39 |
| Source-grounded action I2V | 4 | 4 |
| **Total** | **36** | **65** |

The result therefore contains 43 revised I2V prompts and 22 explicit generative abstentions with deterministic overlay plans. No new video provider was called and nothing was uploaded to S3. Existing reviewed MP4s are linked only as baseline evidence.

The generated prompt and provenance payload is in `tune-manifest.json`; the exact row-level audit input is in `tune-evaluation.json`.

## Validation hypothesis

Fresh human review should evaluate the repair assertion for each target, not merely similarity to an accepted sibling:

- source text/data/layout and product identity remain unchanged;
- entity count, limbs, props, attachments and contact topology are continuous;
- initial state does not reverse and unsupported objects/actions do not appear;
- camera remains a single bounded shot with visible but contained travel;
- model-specific motion is neither imperceptible nor exaggerated;
- compositor cases preserve source pixels and keep the accent inside the declared target bounds.

This release regenerates prompts and exposes the comparison in Step 8. It intentionally does not claim improved video quality until the tuned prompts are rendered and reviewed in a separate generation pass.
