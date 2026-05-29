# AB6 AI Agent API

## Base URL: `/api/v1/ai`

### Events
| Method | Path | Description |
|---|---|---|
| POST | `/events` | Ingest a single observation event |
| POST | `/events/batch` | Ingest batch of observation events |
| POST | `/domain-events` | Ingest a domain event |

### Telemetry
| Method | Path | Description |
|---|---|---|
| WS | `/telemetry/ws` | Real-time robot telemetry stream |

### Interventions
| Method | Path | Description |
|---|---|---|
| WS | `/interventions/{user_id}/ws` | WebSocket for intervention delivery |
| GET | `/interventions/{user_id}/stream` | SSE stream for intervention delivery |

### Agent
| Method | Path | Description |
|---|---|---|
| POST | `/agent/sessions/{user_id}/start` | Start an OODA agent session |
| POST | `/agent/sessions/{user_id}/cycle` | Run one OODA cycle |
| POST | `/agent/sessions/{user_id}/stop` | Stop agent session |
| GET | `/agent/sessions/{user_id}/state` | Get current agent state |

### Concept Graph
| Method | Path | Description |
|---|---|---|
| GET | `/concepts/{concept_id}` | Get concept details |
| GET | `/concepts/{concept_id}/neighbors` | Get prerequisites and dependents |
| GET | `/concepts/{concept_id}/prerequisites` | Get prerequisite chain |
| GET | `/concepts/search?query=...` | Semantic search over concepts |

## WebSocket Protocol

Interventions are delivered as JSON messages:
```json
{
  "intervention_id": "uuid",
  "type": "concept_explanation",
  "content": {"title": "...", "body": "..."},
  "display": {"position": "inline", "priority": "medium"},
  "metadata": {"concept_id": "...", "cycle_number": 0}
}
```
