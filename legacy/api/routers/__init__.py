from legacy.api.routers.events import router as events_router
from legacy.api.routers.telemetry import router as telemetry_router
from legacy.api.routers.interventions import router as interventions_router
from legacy.api.routers.agent import router as agent_router
from legacy.api.routers.concept_graph import router as concept_graph_router

__all__ = [
    "events_router",
    "telemetry_router",
    "interventions_router",
    "agent_router",
    "concept_graph_router",
]
