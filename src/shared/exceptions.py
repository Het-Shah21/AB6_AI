class AB6AIError(Exception):
    pass


class LLMProviderError(AB6AIError):
    pass


class LLMRateLimitError(LLMProviderError):
    pass


class LLMFallbackExhaustedError(LLMProviderError):
    pass


class SanitizationError(AB6AIError):
    pass


class ConceptGraphError(AB6AIError):
    pass


class ConceptGraphCycleError(ConceptGraphError):
    pass


class InterventionError(AB6AIError):
    pass


class InterventionDeliveryError(InterventionError):
    pass


class AgentError(AB6AIError):
    pass


class AgentPauseError(AgentError):
    pass


class MemoryError(AB6AIError):
    pass


class WisdomNotFoundError(MemoryError):
    pass


class IngestionError(AB6AIError):
    pass


class ChallengeGenerationError(AB6AIError):
    pass
