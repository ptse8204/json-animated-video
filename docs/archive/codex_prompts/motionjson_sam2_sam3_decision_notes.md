# SAM2 vs SAM3 Decision Notes for MotionJSON

## Decision

MotionJSON should default to low-cost object discovery with fewer cleaner candidates and selected-candidate tracking.

It should also provide:

- Balanced discovery;
- Maximum recall discovery;
- Trace Everything expert mode.

SAM2 should be the practical default for local/keyframe proposals and video propagation when a real model is configured.

SAM3 should be an optional advanced provider for concept, exemplar, and semantic high-recall discovery.

## Why not start with a text prompt?

The product goal is object motion-layer extraction. Users should not need to know the object name first.

The default user path should be:

```text
Discover objects
→ choose from candidates
→ track selected
→ export JSON motion layers
```

Text prompts should be optional:

```text
Find by text
Find objects like this
```

## Cost Strategy

Cheap first pass:

```text
few keyframes
strict filters
candidate caps
track selected only
review before export
```

Maximum recall pass:

```text
more keyframes
more candidates
looser filters
write rejected candidates
track selected or top candidates only
review before export
```

Trace Everything:

```text
expert/experimental
explicit warning
bounded
review required
not default
```

## SAM2 Role

Use SAM2 for:

- automatic masks on limited keyframes;
- point/box/mask refinement;
- video propagation after user selection;
- interactive correction;
- lower-cost local provider path.

SAM2 limitation:

- It does not naturally find all instances of a text/concept such as “all cups” without detector/concept help.

## SAM3 Role

Use SAM3 for:

- concept prompts;
- exemplar/crop prompts;
- open-vocabulary candidate discovery;
- semantic grouping;
- higher-recall advanced workflows.

SAM3 limitation:

- Heavier local prerequisites;
- should remain optional;
- not the default local-first CPU path;
- hosted usage requires privacy/cost opt-in.

## API-first Rule

The UI should collect intent and render results. The API/backend should own:

- candidate generation;
- candidate filtering;
- candidate rejection reasons;
- track generation;
- diagnostics;
- artifact registration;
- correction state;
- export validation.

If UI demo placeholders are needed, mark them:

```json
{
  "demoMode": true,
  "source": "demo-only",
  "exportable": false
}
```

Never use synthetic UI tracks as normal completed job results.
