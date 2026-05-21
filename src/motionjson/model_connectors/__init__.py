"""Server-side model planning connector contracts for the Local UI.

The default registry keeps deterministic local planning available and exposes
settings-backed hosted provider readiness without making hosted calls.
"""

from .contracts import (
    MODEL_CONNECTOR_FORMAT,
    MODEL_ESTIMATE_FORMAT,
    MODEL_PLAN_FORMAT,
    MODEL_RUN_FORMAT,
    MODEL_RUN_STATUSES,
    FakeModelConnector,
    ModelConnector,
    ModelConnectorError,
    ModelConnectorRegistry,
    ModelEstimate,
    ModelPlanRequest,
    ModelPlanResult,
    ModelProviderDefinition,
    ModelRunEvent,
    ModelRunState,
    OpenAIPlanningConnector,
    OpenRouterSettingsModelConnector,
    VolatileModelRunStore,
)

__all__ = [
    "MODEL_CONNECTOR_FORMAT",
    "MODEL_ESTIMATE_FORMAT",
    "MODEL_PLAN_FORMAT",
    "MODEL_RUN_FORMAT",
    "MODEL_RUN_STATUSES",
    "FakeModelConnector",
    "ModelConnector",
    "ModelConnectorError",
    "ModelConnectorRegistry",
    "ModelEstimate",
    "ModelPlanRequest",
    "ModelPlanResult",
    "ModelProviderDefinition",
    "ModelRunEvent",
    "ModelRunState",
    "OpenAIPlanningConnector",
    "OpenRouterSettingsModelConnector",
    "VolatileModelRunStore",
]
