# Rights Metadata and Asset Lineage

MotionJSON turns useful video elements into reusable motion layers for editors and websites. Phase 13 adds a local commercial safety layer for those reusable layers without adding network calls, paid API calls, legal advice, billing, marketplace behavior, SDKs, webhooks, or public developer APIs.

## Rights Manifest

Every extraction writes `rights_manifest.json` using schema `motionjson.rights_manifest.v0.1`. The manifest contains:

- `source`: the source video URI plus structured source attribution.
- `objects`: one rights block per extracted object.
- `summary`: attribution, license, and commercial-use review status across objects.
- `assetLineage`: extraction operations that produced cached raster/alpha assets and JSON motion.
- `auditLog`: deterministic manifest-level audit records supplied by callers.

Object rights blocks include:

- `sourceAttribution`: required flag, source type, source asset id, source URI, and display text.
- `license` and `licenseDetails`: machine-readable id plus name, URL, and scope.
- `creatorApproval`: approval boolean, status, and evidence records.
- `commercialUse` and `commercialUseStatus`: commercial-use flag and review state.
- `assetLineage`: source-video origin and object-layer extraction operations.
- `auditLog`: local audit records.

Default extraction rights are intentionally conservative: `user_uploaded_unverified`, creator approval `unverified`, and `commercialUseStatus` `review_required`.

## Export Preservation

Scene graphs, object manifests, web asset manifests, final export manifests, Remotion plans, and website ZIP package manifests preserve structured rights. Export surfaces keep `aiUsage: none` because they use cached raster/alpha assets and JSON transforms. Normal drag, scale, rotate, preview, and export paths do not rerun segmentation, matting, LLM, VLM, or hosted AI providers.

Website ZIP packages include:

- `rights_manifest.json`
- `package_manifest.json` with `rightsManifest` and `rightsSummary`
- structured per-object rights under `rights`

## Backend Tables

The local SQLite backend stores:

- `rights_metadata`: rights JSON scoped to assets and/or objects, creator approval fields, and commercial-use status.
- `asset_lineage`: source asset to derived asset edges with job id, operation, object id, and metadata.
- `audit_events`: user, project, job, asset, and object scoped audit events.

Uploads record source rights and an `asset_uploaded` audit event. Extraction records source-video to generated-manifest/cutout lineage plus rights rows for object-scoped generated assets. Website package exports record package lineage, package rights, and a `website_package_exported` audit event.

## CLI Boundaries

Extraction and backend upload/extract commands accept local metadata flags for source attribution, license, creator approval, and commercial use. The backend provides `motionjson backend asset-rights ASSET_ID` for local inspection of rights and lineage rows.

These flags do not call network services and do not establish legal clearance. They only preserve structured metadata so downstream review workflows can make informed decisions.
