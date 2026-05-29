import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def log_agent_event(event_type: str, data: dict) -> None:
    """Log an agent event for observability."""
    logger.info("AGENT_EVENT[%s]: %s", event_type, data)
