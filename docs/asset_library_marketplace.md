# Asset Library And Marketplace Foundation

Phase 18 adds a local asset-library foundation for reusable MotionJSON motion
layers. It is not a public marketplace launch and does not add billing,
commerce, public listings, new AI calls, or paid provider calls.

Phase 11G also exposes these existing primitives in the local UI through an
Asset Library panel. The UI panel saves explicit generated/export artifacts as
`motion_sticker` library assets, searches saved layers, creates brand
collections, attaches selected layers to collections, and attempts
creator-approved pack creation through the same backend rights gate described
below.

MotionJSON turns useful video elements into reusable motion layers for editors
and websites. Photoreal objects remain cached raster/alpha assets by default
and are controlled by JSON transforms. SVG/Lottie stays limited to simple
vector-like silhouettes, labels, annotations, icons, and flat graphics.

## Library Assets

Users can save an existing backend asset as a reusable library asset:

```bash
python -m motionjson.cli backend save-library-asset \
  --project-id PROJECT_ID \
  --asset-id ASSET_ID \
  --type motion_sticker \
  --title "Launch sticker" \
  --tag hero \
  --tag brand \
  --session-token-env MOTIONJSON_SESSION_TOKEN
```

Supported types are:

- `saved_asset`
- `motion_sticker`

Library assets reference existing `assets.id` rows. They do not copy stored
bytes. Public API, CLI, and SDK responses omit `storage_key`, token hashes,
secret hashes, uploaded bytes, and raw key material.

Rights fields are derived from the latest existing `rights_metadata` row for
the saved asset when possible:

- `license`, `licenseName`, `licenseUrl`, `licenseScope`
- `creatorApproved`, `creatorApprovalStatus`
- `commercialUse`, `commercialUseStatus`
- `rightsMetadataId`

If rights metadata is missing, the library asset remains unverified and review
required.

## Search And Filters

List and search library assets locally:

```bash
python -m motionjson.cli backend list-library-assets \
  --q launch \
  --tag hero \
  --license-scope commercial \
  --creator-approved true \
  --commercial-use-status approved \
  --session-token-env MOTIONJSON_SESSION_TOKEN
```

REST:

```http
GET /v1/library/assets?q=&tag=&license=&licenseScope=&creatorApproved=&commercialUseStatus=&collectionId=&packId=
```

Local UI route:

```http
GET /api/library/assets?q=&tag=&creatorApproved=&commercialUseStatus=&collectionId=&packId=
```

Search uses deterministic SQLite `LIKE` matching over title, description,
license, and tags. It does not use external search services.

## Brand Collections

Brand collections group saved library assets:

```bash
python -m motionjson.cli backend create-brand-collection \
  --project-id PROJECT_ID \
  --title "Spring launch" \
  --session-token-env MOTIONJSON_SESSION_TOKEN

python -m motionjson.cli backend add-collection-asset \
  --collection-id COLLECTION_ID \
  --library-asset-id LIBRARY_ASSET_ID \
  --session-token-env MOTIONJSON_SESSION_TOKEN
```

Collections are user-scoped. Optional `projectId` values are checked against
the authenticated user before a collection is created.

## Creator-Approved Packs

Creator packs are assembled from assets already attached to a brand collection:

```bash
python -m motionjson.cli backend create-creator-pack \
  --collection-id COLLECTION_ID \
  --title "Approved launch pack" \
  --session-token-env MOTIONJSON_SESSION_TOKEN
```

Pack creation rejects any asset unless the saved library asset has:

- `creatorApprovalStatus: approved`
- `creatorApproved: true`
- `commercialUseStatus: approved`
- `commercialUse: true`

These fields come from `rights_metadata`; the pack workflow does not override
or mint rights.

## API And SDK

REST endpoints:

- `POST /v1/projects/{projectId}/library-assets`
- `GET /v1/library/assets`
- `GET /v1/library/assets/{libraryAssetId}`
- `POST /v1/library/collections`
- `GET /v1/library/collections`
- `POST /v1/library/collections/{collectionId}/assets`
- `GET /v1/library/collections/{collectionId}/assets`
- `POST /v1/library/packs`
- `GET /v1/library/packs`

The dependency-light local UI mirrors the same workflow under `/api/` for the
reserved local UI user:

- `POST /api/projects/{projectId}/library-assets`
- `GET /api/library/assets`
- `GET /api/library/assets/{libraryAssetId}`
- `POST /api/library/collections`
- `GET /api/library/collections`
- `POST /api/library/collections/{collectionId}/assets`
- `GET /api/library/collections/{collectionId}/assets`
- `POST /api/library/packs`
- `GET /api/library/packs`

JavaScript SDK helpers:

```js
await client.saveLibraryAsset(project.id, {
  assetId: asset.id,
  type: "motion_sticker",
  title: "Launch sticker",
  tags: ["hero", "brand"]
});

await client.listLibraryAssets({
  q: "launch",
  tag: "hero",
  licenseScope: "commercial",
  creatorApproved: true,
  commercialUseStatus: "approved"
});

const collection = await client.createBrandCollection({
  projectId: project.id,
  title: "Spring launch"
});
await client.addCollectionAsset(collection.id, { libraryAssetId: "..." });
await client.createCreatorPack({
  collectionId: collection.id,
  title: "Approved launch pack"
});
```

All normal save, list, search, collection, and pack responses include
`aiUsage: "none"`. These operations use cached database rows and JSON metadata;
they do not call segmentation, matting, OpenRouter, hosted providers, or paid
APIs.

## Validation

```bash
pytest -q tests/test_backend_asset_library.py tests/test_backend_api_product.py tests/test_backend_rights_lineage.py
pytest -q
npm test
npm run lint
git diff --check
```
