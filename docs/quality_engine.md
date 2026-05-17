# Quality Engine

The quality engine scores extracted object layers from generated extraction metadata only. It does not call AI providers, segmentation providers, matting providers, render providers, network APIs, or paid services. Normal drag, scale, rotate, opacity, and timeline preview stay on cached raster/alpha assets plus JSON transforms.

## Inputs

Scores are computed from per-frame metadata already emitted by extraction:

- `visible`
- `area`
- `bbox`
- `centroid`
- `contour_points`
- `polygon`

Invisible or missing frames may have `bbox: null`, `centroid: null`, empty `polygon`, and `area: 0`.

## Quality Contract

Every core quality object includes these bounded `0..1` scores, rounded to four decimal places:

- `maskStability`: high-is-good compatibility score for area, bbox, and drift stability.
- `edgeComplexity`: low-is-good compatibility score for contour complexity.
- `bboxStability`: high-is-good bbox size stability score.
- `maskDriftScore`: high-is-good temporal mask consistency from area, bbox, and centroid motion.
- `edgeQualityScore`: high-is-good outline quality score for simple, stable edges.
- `missingFrameScore`: high-is-good visible-frame coverage score with an extra penalty for long gaps.
- `occlusionRiskScore`: high-is-risk score from missing frames, long gaps, area dips, and jitter.
- `vectorSuitability`: high-is-good score for optional vector silhouette assistance.
- `productionReadinessScore`: high-is-good score for production handoff confidence.

Quality diagnostics also include:

- `visibleFrameRatio`
- `missingFrameRatio`
- `longestMissingFrameRun`
- `productionReadiness`: `ready`, `review`, or `needs_correction`
- `routingReasons`

## Readiness Rules

`productionReadinessScore` is a weighted score across mask stability, edge quality, bbox stability, missing-frame coverage, and occlusion risk.

Readiness labels are conservative:

- `ready`: score is at least `0.82`, missing risk is low, and occlusion risk is low.
- `review`: score is at least `0.55`, but the layer still needs human review.
- `needs_correction`: score is below review level or force-down rules apply.

Force-down rules prevent apparently good average scores from hiding extraction gaps:

- Missing-frame ratio at or above `0.40`, longest missing run at or above `4`, or occlusion risk at or above `0.75` forces `needs_correction`.
- Missing-frame ratio at or above `0.15`, longest missing run at or above `2`, or occlusion risk at or above `0.45` caps readiness at review level.

## Routing

The default route is always `raster_alpha_sequence`.

`hybrid_vector_silhouette_plus_raster` is allowed only when the layer has high vector suitability, high production readiness, high missing-frame coverage, low occlusion risk, high mask drift consistency, and strong edge quality. This route still keeps the photoreal object as cached raster/alpha assets; the vector portion is for simple silhouette assistance.

MotionJSON never recommends pure SVG or pure Lottie for extracted photoreal objects.

## Export Routing

Validated local UI exports turn the quality scores into an explicit
`quality_routing.json` report. The report chooses raster alpha by default,
enables vector silhouette assistance only when `recommendedOutput` and the
export preset both allow contours, and selects a ready sprite atlas, AVIF atlas,
or transparent WebM delivery when cached production assets are available.

MP4 preview routing is reported separately. A missing FFmpeg binary or encoder
failure is surfaced as `unavailable` or `error` instead of hiding the issue or
blocking the JSON handoff. Export routing is deterministic and uses only cached
artifacts, resource profile data, and JSON transforms.
