from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

PLAN_CATALOG: list[dict[str, Any]] = [
    {
        "id": "starter",
        "name": "Starter",
        "audience": "Individual editors validating object-layer workflows locally.",
        "monthlyPriceUsd": 0,
        "billingInterval": "monthly",
        "entitlements": {
            "projects": 3,
            "monthlyExtractFrames": 1200,
            "assetStorageGb": 5,
            "webhookEndpoints": 2,
            "creatorPacks": 1,
            "seats": 1,
        },
        "features": [
            "Local backend and SQLite metadata",
            "Cached raster/alpha motion layers",
            "JSON transform editing and preview",
            "Website ZIP and Remotion plan exports",
        ],
    },
    {
        "id": "studio",
        "name": "Studio",
        "audience": "Small creative teams preparing reusable web and editor assets.",
        "monthlyPriceUsd": 49,
        "billingInterval": "monthly",
        "entitlements": {
            "projects": 25,
            "monthlyExtractFrames": 18000,
            "assetStorageGb": 100,
            "webhookEndpoints": 10,
            "creatorPacks": 10,
            "seats": 5,
        },
        "features": [
            "Brand collections and creator-approved packs",
            "Support and redacted error reporting",
            "Signed webhook delivery records",
            "Production asset package workflows",
        ],
    },
    {
        "id": "production",
        "name": "Production",
        "audience": "Teams embedding reusable motion layers into shipped products.",
        "monthlyPriceUsd": 199,
        "billingInterval": "monthly",
        "entitlements": {
            "projects": 250,
            "monthlyExtractFrames": 240000,
            "assetStorageGb": 1000,
            "webhookEndpoints": 50,
            "creatorPacks": 100,
            "seats": 25,
        },
        "features": [
            "Higher local entitlement limits",
            "Deployment and security checklist support",
            "API and SDK routes for status checks",
            "Vendor-neutral provider boundaries",
        ],
    },
]


def list_plan_catalog() -> dict[str, Any]:
    return {
        "plans": deepcopy(PLAN_CATALOG),
        "billingProvider": "local_catalog",
        "paymentCollection": "not_configured",
        "checkout": "out_of_scope",
        "aiUsage": "none",
    }


def _default_plan_id() -> str:
    configured = os.environ.get("MOTIONJSON_DEFAULT_PLAN", "starter").strip().lower()
    available = {plan["id"] for plan in PLAN_CATALOG}
    return configured if configured in available else "starter"


def _plan_by_id(plan_id: str) -> dict[str, Any]:
    for plan in PLAN_CATALOG:
        if plan["id"] == plan_id:
            return deepcopy(plan)
    return deepcopy(PLAN_CATALOG[0])


def get_billing_status(*, user_id: str) -> dict[str, Any]:
    plan = _plan_by_id(_default_plan_id())
    return {
        "userId": user_id,
        "plan": plan,
        "subscription": {
            "state": "catalog_only",
            "planId": plan["id"],
            "managedBy": "local_configuration",
            "renewsAt": None,
            "trialEndsAt": None,
        },
        "entitlements": deepcopy(plan["entitlements"]),
        "billingProvider": "local_catalog",
        "paymentCollection": "not_configured",
        "checkout": "out_of_scope",
        "aiUsage": "none",
    }
