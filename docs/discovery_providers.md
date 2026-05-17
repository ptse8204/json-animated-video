# Discovery Providers

Phase 5 adds object-candidate discovery providers for workflows that need more
than one manually selected object. Discovery providers output the shared
`ObjectCandidate` shape first; segmentation/tracking still happens through the
provider pipeline.

SAM2 is promptable segmentation/tracking, not semantic discovery by itself.
Text and class workflows must use detector candidates before a mask/tracker
provider receives boxes or masks.

## Modes

- `manual_prompt`: use when a user marks one or more objects with points,
  boxes, or mask references. No model is required.
- `motion_foreground`: use for simple footage where moving objects separate
  from a mostly stable background. This CPU mode writes generated mask
  sequences under `discovery/motion_foreground/`.
- `external_masks`: use when masks or boxes already exist from another local
  tool. It imports one candidate per object mask directory or manifest entry.
- `sam_auto_masks`: scaffold for automatic keyframe mask proposals. It is
  capability-gated behind optional SAM2/torch/model configuration and has a
  mock mode for tests.
- `text_detector`: scaffold for open-vocabulary detection. Missing detector
  packages or model paths are capability warnings; mock mode can produce local
  boxes for UI smoke checks.
- `class_detector`: scaffold for known-class detection. Missing optional
  detector packages are reported in diagnostics; mock mode is local-only.

## When To Use And Failure Modes

| Mode | Use When | Common Failure Mode | Safer Fallback |
| --- | --- | --- | --- |
| `manual_prompt` | One known object needs a point, box, or mask prompt. | Prompt is too loose and returns background or whole-frame masks. | Add a tighter box or use external masks. |
| `motion_foreground` | The camera is mostly still and objects move. | Camera motion or shadows become candidates. | Use `external_masks` or review/delete extra tracks. |
| `external_masks` | Masks or boxes already exist from another local tool. | Mask sequence is missing frames or points at the wrong object. | Validate each object ID and inspect `fallback_diagnostics.json`. |
| `sam_auto_masks` | A configured SAM2-style backend should propose visible segments. | Background fragments, floor/wall masks, or missing SAM2 weights. | Use filters, mock mode, or a detector-first workflow. |
| `text_detector` | Users describe objects with text labels. | Detector package/model is missing or boxes are semantically wrong. | Use mock smoke tests, class detector, or manual/external masks. |
| `class_detector` | Known classes are enough for the video domain. | YOLO/known-class model is unavailable or returns too many classes. | Limit classes, lower max candidates, or use manual review. |

## UI vs CLI Support Today

| Workflow | CLI support | Local UI job support |
| --- | --- | --- |
| `manual_prompt` + `threshold`/`external`/`mock` | Runnable with base CPU dependencies. | Runnable through the local worker. |
| `motion_foreground` / `motion` | Runnable from the CLI as a CPU/no-model path. | Visible in the wizard, but the current local UI worker does not start `motion` jobs yet. |
| `external_masks` | Runnable when mask directories or a manifest are supplied. | Runnable when the selected local asset has a mask directory configured. |
| `text_detector` and `class_detector` | Mock mode is runnable; real detector backends are scaffolded until configured and wired. | Shown as mock/scaffolded presets so users can preview the flow without claiming real detection. |
| `sam_auto_masks` | Mock mode is runnable; real automatic masks need a SAM2-style backend. | Shown as a mock/scaffolded preset until a runnable backend is available. |

## CLI Examples

CPU moving-region discovery:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/motion_discovery \
  --discovery-provider motion_foreground \
  --discovery-min-area 20 \
  --discovery-max-candidates 3 \
  --max-frames 12
```

External mask discovery from a manifest:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/external_discovery \
  --discovery-provider external_masks \
  --discovery-config '{"objects":[{"object_id":"ball","label":"Red ball","mask_dir":"masks/ball"}]}'
```

Text detector mock smoke check:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/text_mock \
  --discovery-provider text_detector \
  --discovery-text "red ball . hand" \
  --discovery-config '{"mock":true}' \
  --max-frames 2
```

## Candidate Shape

`candidates.json` records:

- `id`, `label`, `source`, `frameIndex`, `zIndex`;
- optional `point`, `box`, `maskRef`, and `score`;
- provider metadata including UI descriptions, filter settings, and `maskDir`
  when the candidate can feed the current mask-tracking pipeline directly.

Candidates with `metadata.maskDir` are adapted into `ObjectExtractionSpec`
values backed by `ExternalMaskProvider`, then processed by the shared
tracking/vectorization/export path.

## Capability Behavior

Run diagnostics before presenting discovery choices:

```bash
python3 -m motionjson.cli backend diagnostics --json
```

`manual_prompt`, `motion_foreground`, and `external_masks` are no-model local
providers when base dependencies are installed. `sam_auto_masks`,
`text_detector`, and `class_detector` are scaffolded heavy-provider surfaces:
they report `missing_dependency`, `missing_model`, or `not_configured` until a
real backend adapter is wired and configured. Those warnings do not break the
base CLI, and mock mode remains available for local smoke checks.
