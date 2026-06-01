# Phase 2 — LLM Integration: System Design Diagrams

Phase 2 wraps every LLM call behind a single, fault-tolerant provider factory.
Everything that needs an LLM (`orient`, `decide`, `act`, `builder`,
`generator`) goes through `get_llm_for_purpose()`.

---

## 2.1 — Provider Fallback Chain

Three independent providers, one logical interface. If provider A fails the
system seamlessly tries B, then C.

```mermaid
flowchart TB
    C["Caller<br/>(agent node / builder / generator)"]
    C --> P["get_llm_for_purpose(purpose)"]
    P --> RL["RateLimiter.acquire(provider)"]
    RL --> TRY1

    TRY1{{"Try #1<br/>primary"}}:::try
    TRY1 -->|success| M1["init_chat_model(<b>openai:gpt-4o-mini</b>)"]
    TRY1 -->|fail / no key| TRY2

    TRY2{{"Try #2<br/>fallback_1"}}:::try
    TRY2 -->|success| M2["init_chat_model(<b>anthropic:claude-sonnet-4-20250514</b>)"]
    TRY2 -->|fail| TRY3

    TRY3{{"Try #3<br/>fallback_2"}}:::try
    TRY3 -->|success| M3["init_chat_model(<b>google_genai:gemini-2.5-flash</b>)"]
    TRY3 -->|fail| ERR["raise LLMFallbackExhaustedError"]

    M1 --> OUT["BaseChatModel returned to caller"]
    M2 --> OUT
    M3 --> OUT
    ERR --> CATCH["Caller catches & uses<br/>hardcoded fallback text"]

    classDef try fill:#fef9c3,stroke:#a16207
```

---

## 2.2 — Purpose-to-Model Routing

The same factory switches model class based on **purpose**, not call-site.
Decisions are cheap, diagnoses are smart.

```mermaid
flowchart LR
    subgraph P["LLM_CONFIG (src/config/llm_config.py)"]
        P1["primary<br/>openai:gpt-4o-mini"]
        P2["reasoning<br/>openai:gpt-4o"]
        P3["fallback_1<br/>anthropic:claude-sonnet-4-20250514"]
        P4["fallback_2<br/>google_genai:gemini-2.5-flash"]
        P5["embedding<br/>openai:text-embedding-3-small"]
    end

    P1 -->|"get_llm_for_purpose('primary')"| DECIDE["decide.py<br/>(cheap decisions)"]
    P2 -->|"get_llm_for_purpose('reasoning')"| ORIENT["orient.py<br/>(deep diagnosis)"]
    P2 --> ACT["act.py<br/>(payload generation)"]
    P3 -. "fallback for primary or reasoning" .- DECIDE
    P3 -. "fallback" .- ORIENT
    P4 -. "fallback" .- DECIDE
    P4 -. "fallback" .- ORIENT
    P5 -->|"OpenAIEmbeddings()"| EMB["concept_graph/embeddings.py"]
    P5 -->|"aembed_query / aembed_documents"| CB["concept_graph/builder.py"]
```

---

## 2.3 — Sliding-Window Rate Limiter

Per-provider 100 RPM cap. Each provider gets its own lock so they don't
interfere with each other.

```mermaid
flowchart TB
    A["acquire('openai')"] --> L["acquire lock for 'openai'"]
    L --> S1["t = now()"]
    S1 --> S2["drop timestamps older than<br/>now - 60 s"]
    S2 --> Q{"len(timestamps) >= rpm?"}
    Q -- No --> APP["append now()<br/>release lock"]
    Q -- Yes --> SL["sleep until oldest<br/>timestamp exits window"]
    SL --> S2
    APP --> OUT["return (caller proceeds)"]
```

---

## 2.4 — PII Sanitizer Pipeline

All LLM-bound text is scrubbed through a 4-stage regex chain **before**
leaving the application boundary.

```mermaid
flowchart LR
    IN["Input text / dict"] --> S0["json.dumps() (if dict)"]
    S0 --> S1["EMAIL_PATTERN.sub<br/>[REDACTED-EMAIL]"]
    S1 --> S2["PHONE_PATTERN.sub<br/>[REDACTED-PHONE]"]
    S2 --> S3["CC_PATTERN.sub<br/>[REDACTED-CC]"]
    S3 --> S4["NAME_PATTERN.sub<br/>[REDACTED-NAME]"]
    S4 --> OUT["Clean string"]
    OUT --> LLM["Sent to LLM<br/>via provider.py"]

    M1["sanitize_observation_event()"] --> S0
    M2["sanitize_learner_summary()"] --> S0
    MW["PII Middleware (api/middleware/sanitizer.py)"] --> S0
```

> **Design note:** `NAME_PATTERN` requires the prefix `name:|` `user:|` `student:`
> so legitimate concept names like "Inverse Kinematics" are preserved.

---

## 2.5 — Where LLM Calls Happen Across the System

```mermaid
flowchart TB
    subgraph AGENT["Phase 5 — OODA Agent"]
        OR["orient.py"]
        DE["decide.py<br/>(Thompson sampling, no LLM)"]
        AC["act.py"]
    end
    subgraph KB["Phase 4 — Concept Graph"]
        BU["builder.py<br/>(extract + edge inference)"]
        EM["embeddings.py"]
    end
    subgraph INT["Phase 7 — Intervention"]
        GEN["generator.py<br/>(challenge / explanation)"]
    end
    subgraph API["Phase 8 — API"]
        MW["middleware/sanitizer.py"]
    end

    OR -->|"reasoning"| P
    AC -->|"reasoning"| P
    BU -->|"reasoning / primary"| P
    EM -->|"embedding model"| P
    GEN -->|"reasoning / primary"| P
    MW -->|"strip PII before LLM"| P

    P["src/llm/provider.py<br/>get_llm_for_purpose()"]
    P --> RL["RateLimiter"]
    P --> FB["Fallback chain"]
    FB --> OA["OpenAI"]
    FB --> AN["Anthropic"]
    FB --> GG["Google GenAI"]
```

---

## 2.6 — Defense-in-Depth: What Happens When No API Key Is Set

This is the actual runtime path during the offline demo.

```mermaid
sequenceDiagram
    autonumber
    participant Node as ORIENT node
    participant P as provider.py
    participant RL as RateLimiter
    participant OAI as OpenAI
    participant ANT as Anthropic
    participant GEM as Google

    Node->>P: get_llm_for_purpose("reasoning")
    P->>RL: acquire("openai")
    P->>OAI: init_chat_model("openai:gpt-4o")
    OAI-->>P: ❌ Auth error (no key)
    P-->>P: log warning "openai failed"
    P->>ANT: init_chat_model("anthropic:claude-sonnet-4-20250514")
    ANT-->>P: ❌ Auth error
    P->>GEM: init_chat_model("google_genai:gemini-2.5-flash")
    GEM-->>P: ❌ Auth error
    P-->>Node: raise LLMFallbackExhaustedError
    Node->>Node: except LLMFallbackExhaustedError<br/>use hardcoded fallback text
```

---

## 2.7 — Phase 2 Component Map

```mermaid
flowchart LR
    subgraph P2["src/llm/"]
        PROV["provider.py<br/>(factory + fallback)"]
        RATE["rate_limiter.py<br/>(sliding window)"]
        SAN["sanitizer.py<br/>(PII regex)"]
    end
    subgraph CFG["src/config/"]
        SET["settings.py"]
        LCFG["llm_config.py"]
    end
    SET -->|"get_settings()"| PROV
    LCFG --> PROV
    PROV --> RATE
    PROV --> EX["shared/exceptions.py<br/>LLMFallbackExhaustedError"]
```
