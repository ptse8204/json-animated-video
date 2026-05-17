from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exporters.scene_graph import write_json

RIGHTS_MANIFEST_SCHEMA = "motionjson.rights_manifest.v0.1"


def _source_attribution_summary(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return {
            "required": bool(raw.get("required", True)),
            "sourceType": raw.get("sourceType") or "user_upload",
            "sourceAssetId": raw.get("sourceAssetId"),
            "sourceUri": raw.get("sourceUri") or "",
            "displayText": raw.get("displayText") or "User uploaded source video",
        }
    if isinstance(raw, bool):
        return {
            "required": raw,
            "sourceType": "user_upload",
            "sourceAssetId": None,
            "sourceUri": "",
            "displayText": "User uploaded source video",
        }
    return {
        "required": True,
        "sourceType": "user_upload",
        "sourceAssetId": None,
        "sourceUri": "",
        "displayText": "User uploaded source video",
    }


@dataclass(frozen=True)
class RightsContext:
    source_type: str = "user_upload"
    source_asset_id: str | None = None
    source_uri: str | None = None
    display_text: str = "User uploaded source video"
    attribution_required: bool = True
    license: str = "user_uploaded_unverified"
    license_name: str = "User uploaded - rights unverified"
    license_url: str | None = None
    license_scope: str = "unknown"
    creator_approved: bool = False
    creator_approval_status: str = "unverified"
    creator_approval_evidence: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    commercial_use: bool = False
    commercial_use_status: str | None = None
    audit_log: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def normalize_rights_context(
    context: RightsContext | dict[str, Any] | None = None,
    *,
    fallback_source_uri: str | Path | None = None,
) -> RightsContext:
    if isinstance(context, RightsContext):
        if context.source_uri or fallback_source_uri is None:
            return context
        return RightsContext(**{**context.__dict__, "source_uri": str(fallback_source_uri)})
    if context is None:
        raw: dict[str, Any] = {}
    elif isinstance(context, dict):
        raw = dict(context)
    else:
        raise TypeError("rights context must be a RightsContext, dict, or None")

    source_attribution_raw = raw.get("sourceAttribution")
    source_attribution = source_attribution_raw if isinstance(source_attribution_raw, dict) else {}
    license_details = raw.get("licenseDetails") if isinstance(raw.get("licenseDetails"), dict) else {}
    creator_approval = raw.get("creatorApproval") if isinstance(raw.get("creatorApproval"), dict) else {}
    if isinstance(source_attribution_raw, bool):
        attribution_required = source_attribution_raw
    else:
        attribution_required = bool(source_attribution.get("required", raw.get("attribution_required", True)))

    commercial_use = bool(raw.get("commercialUse", raw.get("commercial_use", False)))
    creator_approved = bool(creator_approval.get("approved", raw.get("creator_approved", False)))
    status = raw.get("commercialUseStatus") or raw.get("commercial_use_status")

    return RightsContext(
        source_type=str(source_attribution.get("sourceType") or raw.get("source_type") or "user_upload"),
        source_asset_id=source_attribution.get("sourceAssetId") or raw.get("source_asset_id"),
        source_uri=str(source_attribution.get("sourceUri") or raw.get("source_uri") or fallback_source_uri or ""),
        display_text=str(source_attribution.get("displayText") or raw.get("display_text") or "User uploaded source video"),
        attribution_required=attribution_required,
        license=str(raw.get("license") or "user_uploaded_unverified"),
        license_name=str(license_details.get("name") or raw.get("license_name") or "User uploaded - rights unverified"),
        license_url=license_details.get("url") or raw.get("license_url"),
        license_scope=str(license_details.get("scope") or raw.get("license_scope") or "unknown"),
        creator_approved=creator_approved,
        creator_approval_status=str(creator_approval.get("status") or raw.get("creator_approval_status") or ("approved" if creator_approved else "unverified")),
        creator_approval_evidence=tuple(creator_approval.get("evidence") or raw.get("creator_approval_evidence") or ()),
        commercial_use=commercial_use,
        commercial_use_status=str(status or ("approved" if commercial_use and creator_approved else "review_required")),
        audit_log=tuple(raw.get("auditLog") or raw.get("audit_log") or ()),
    )


def build_source_attribution(context: RightsContext) -> dict[str, Any]:
    return {
        "required": context.attribution_required,
        "sourceType": context.source_type,
        "sourceAssetId": context.source_asset_id,
        "sourceUri": context.source_uri or "",
        "displayText": context.display_text,
    }


def build_object_rights(
    *,
    object_id: str,
    context: RightsContext | dict[str, Any] | None = None,
    operations: list[dict[str, Any]] | None = None,
    fallback_source_uri: str | Path | None = None,
) -> dict[str, Any]:
    normalized = normalize_rights_context(context, fallback_source_uri=fallback_source_uri)
    lineage_operations = copy.deepcopy(operations) if operations is not None else None
    if lineage_operations is None:
        lineage_operations = [
            {
                "operation": "extract_object_layer",
                "objectId": object_id,
                "inputs": ["source_video"],
                "outputs": ["cached_raster_alpha_cutouts", "mask_sequence", "json_motion"],
            }
        ]
    return {
        "sourceAttribution": build_source_attribution(normalized),
        "license": normalized.license,
        "licenseDetails": {
            "name": normalized.license_name,
            "url": normalized.license_url,
            "scope": normalized.license_scope,
        },
        "creatorApproval": {
            "approved": normalized.creator_approved,
            "status": normalized.creator_approval_status,
            "evidence": list(copy.deepcopy(normalized.creator_approval_evidence)),
        },
        "commercialUse": normalized.commercial_use,
        "commercialUseStatus": normalized.commercial_use_status or "review_required",
        "assetLineage": {
            "origin": "source_video",
            "operations": lineage_operations,
        },
        "auditLog": list(copy.deepcopy(normalized.audit_log)),
    }


def rights_summary(objects: dict[str, dict[str, Any]]) -> dict[str, Any]:
    review_required = []
    attribution_required = []
    licenses = set()
    for object_id, rights in objects.items():
        if rights.get("commercialUseStatus") != "approved":
            review_required.append(object_id)
        if _source_attribution_summary(rights.get("sourceAttribution"))["required"]:
            attribution_required.append(object_id)
        if rights.get("license"):
            licenses.add(str(rights["license"]))
    return {
        "objectCount": len(objects),
        "commercialUseApproved": not review_required,
        "commercialUseReviewRequired": sorted(review_required),
        "attributionRequired": sorted(attribution_required),
        "licenses": sorted(licenses),
    }


def rights_review_summary(rights: dict[str, Any]) -> dict[str, Any]:
    source = _source_attribution_summary(rights.get("sourceAttribution"))
    license_details = rights.get("licenseDetails") if isinstance(rights.get("licenseDetails"), dict) else {}
    creator_approval = rights.get("creatorApproval") if isinstance(rights.get("creatorApproval"), dict) else {}
    return {
        "sourceAttribution": {
            "required": source["required"],
            "sourceType": source["sourceType"],
            "sourceAssetId": source.get("sourceAssetId"),
            "sourceUri": source["sourceUri"],
            "displayText": source["displayText"],
        },
        "license": rights.get("license") or "user_uploaded_unverified",
        "licenseName": license_details.get("name") or "User uploaded - rights unverified",
        "licenseUrl": license_details.get("url"),
        "licenseScope": license_details.get("scope") or "unknown",
        "creatorApproved": bool(creator_approval.get("approved")),
        "creatorApprovalStatus": creator_approval.get("status") or "unverified",
        "commercialUse": bool(rights.get("commercialUse")),
        "commercialUseStatus": rights.get("commercialUseStatus") or "review_required",
        "attributionRequired": source["required"],
        "lineageOperationCount": len(rights.get("assetLineage", {}).get("operations", [])) if isinstance(rights.get("assetLineage"), dict) else 0,
    }


def rights_warning_items(objects: dict[str, dict[str, Any]], *, labels: dict[str, str] | None = None) -> list[dict[str, Any]]:
    labels = labels or {}
    warnings: list[dict[str, Any]] = []
    for object_id, rights in objects.items():
        label = labels.get(object_id) or object_id
        summary = rights_review_summary(rights)
        if summary["commercialUseStatus"] != "approved":
            warnings.append(
                {
                    "code": "commercial_use_review_required",
                    "severity": "warn",
                    "objectId": object_id,
                    "label": label,
                    "message": f"{label} requires commercial-use review before external handoff.",
                    "suggestedAction": "Confirm source rights or mark commercial-use approval before publishing.",
                }
            )
        if not summary["creatorApproved"] or summary["creatorApprovalStatus"] != "approved":
            warnings.append(
                {
                    "code": "creator_approval_unverified",
                    "severity": "warn",
                    "objectId": object_id,
                    "label": label,
                    "message": f"{label} does not have verified creator approval.",
                    "suggestedAction": "Attach creator approval evidence or keep the export internal.",
                }
            )
        if summary["license"] == "user_uploaded_unverified" or summary["licenseScope"] == "unknown":
            warnings.append(
                {
                    "code": "license_unverified",
                    "severity": "warn",
                    "objectId": object_id,
                    "label": label,
                    "message": f"{label} uses unverified or unknown license metadata.",
                    "suggestedAction": "Review the source license and update rights metadata before external use.",
                }
            )
        if summary["attributionRequired"]:
            warnings.append(
                {
                    "code": "attribution_required",
                    "severity": "info",
                    "objectId": object_id,
                    "label": label,
                    "message": f"{label} requires source attribution.",
                    "suggestedAction": "Carry attribution text into downstream publishing surfaces.",
                }
            )
    return warnings


def build_rights_review_report(*, scene: dict[str, Any], source_asset_id: str | None = None) -> dict[str, Any]:
    objects = scene.get("objects") if isinstance(scene.get("objects"), list) else []
    rights_by_object: dict[str, dict[str, Any]] = {}
    labels: dict[str, str] = {}
    object_summaries: list[dict[str, Any]] = []
    for index, obj in enumerate(objects):
        if not isinstance(obj, dict):
            continue
        object_id = str(obj.get("id") or obj.get("objectId") or f"object_{index}")
        rights = obj.get("rights") if isinstance(obj.get("rights"), dict) else {}
        rights_by_object[object_id] = copy.deepcopy(rights)
        labels[object_id] = str(obj.get("label") or object_id)
        object_summaries.append(
            {
                "objectId": object_id,
                "label": labels[object_id],
                **rights_review_summary(rights),
            }
        )
    return {
        "format": "motionjson.export_rights_summary.v0.1",
        "rightsManifest": scene.get("rightsManifest", "rights_manifest.json"),
        "sourceAssetId": source_asset_id,
        "summary": rights_summary(rights_by_object),
        "objects": object_summaries,
        "warnings": rights_warning_items(rights_by_object, labels=labels),
        "aiUsage": "none",
    }


def build_rights_manifest(
    *,
    source: dict[str, Any],
    objects: list[dict[str, Any]] | dict[str, dict[str, Any]],
    context: RightsContext | dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_rights_context(context, fallback_source_uri=source.get("video"))
    if isinstance(objects, dict):
        object_rights = copy.deepcopy(objects)
    else:
        object_rights = {str(obj.get("id")): copy.deepcopy(obj.get("rights", {})) for obj in objects if obj.get("id")}
    operations = []
    audit_log = list(copy.deepcopy(normalized.audit_log))
    for object_id, rights in object_rights.items():
        for operation in rights.get("assetLineage", {}).get("operations", []):
            item = copy.deepcopy(operation)
            item.setdefault("objectId", object_id)
            operations.append(item)
        audit_log.extend(copy.deepcopy(rights.get("auditLog", [])))
    return {
        "schema": RIGHTS_MANIFEST_SCHEMA,
        "version": "0.1.0",
        "source": {
            "video": source.get("video") or normalized.source_uri or "",
            "sourceAttribution": build_source_attribution(normalized),
        },
        "objects": object_rights,
        "summary": rights_summary(object_rights),
        "assetLineage": {
            "origin": "source_video",
            "operations": operations,
        },
        "auditLog": audit_log,
    }


def write_rights_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    write_json(path, manifest)
