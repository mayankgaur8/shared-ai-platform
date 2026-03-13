# System Diagrams — Shared AI Interface Backend

> All diagrams rendered in Mermaid. Paste into any Mermaid-compatible renderer
> (GitHub, mermaid.live, VS Code Mermaid Preview extension).

---

## 1. System Architecture Diagram

```mermaid
graph TB
    subgraph CLIENT_APPS["Client Applications"]
        direction LR
        APP1[EduAI]
        APP2[Interview Prep]
        APP3[Resume Builder]
        APP4[Health Assistant]
        APP5[Astrology App]
    end

    subgraph GATEWAY["API Gateway Layer"]
        AGW[Azure APIM / Kong<br/>Rate Limiting · SSL · Routing]
    end

    subgraph AUTH["Auth Layer"]
        AUT[Auth Service<br/>JWT · OAuth2 · RBAC · App Identity]
    end

    subgraph CORE["Orchestration Engine (FastAPI)"]
        direction TB
        ORC[Workflow Executor]
        PRM[Prompt Registry + Renderer]
        SAF[Safety Middleware<br/>Pre · Post]
        MRT[Model Router]
        CTX[Context Builder]
        MEM[Memory Service]
    end

    subgraph ADAPTERS["Inference Adapters"]
        direction LR
        OLA[Ollama Adapter]
        OAI[OpenAI Adapter]
        FUT[Future Adapters...]
    end

    subgraph MODELS["AI Models"]
        direction LR
        OLM[Ollama<br/>GPU VM]
        GPT[OpenAI API]
    end

    subgraph DATA["Data Layer"]
        direction LR
        PG[(PostgreSQL<br/>Main DB + pgvector)]
        RD[(Redis<br/>Cache + Queue)]
        QD[(Qdrant<br/>Vector DB)]
        BS[(Azure Blob<br/>Documents)]
    end

    subgraph OBS["Observability"]
        direction LR
        LOG[Structured Logs<br/>structlog]
        TRC[Distributed Traces<br/>OpenTelemetry]
        MET[Metrics<br/>Prometheus + Grafana]
    end

    subgraph JOBS["Background Jobs (Celery)"]
        direction LR
        EMB[Embedding Job]
        AGG[Usage Aggregation]
        SUM[Memory Summarizer]
        HLT[Health Check]
    end

    subgraph ADMIN["Admin Control Plane"]
        ADM[Admin Dashboard<br/>React]
    end

    CLIENT_APPS --> GATEWAY
    GATEWAY --> AUTH
    AUTH --> CORE
    ORC --> PRM
    ORC --> SAF
    ORC --> MRT
    ORC --> CTX
    CTX --> MEM
    MRT --> ADAPTERS
    OLA --> OLM
    OAI --> GPT
    CORE --> DATA
    CORE --> OBS
    CORE --> JOBS
    ADMIN --> CORE
```

---

## 2. Request Flow Diagram

```mermaid
sequenceDiagram
    participant CA as Client App
    participant GW as API Gateway
    participant AS as Auth Service
    participant SM as Safety Middleware
    participant WE as Workflow Executor
    participant PR as Prompt Renderer
    participant MR as Model Router
    participant CB as Context Builder
    participant MS as Memory Service
    participant AD as Adapter (Ollama/OpenAI)
    participant LS as Logging Service

    CA->>GW: POST /v1/generate {workflow, inputs}
    GW->>GW: Rate limit check
    GW->>AS: Validate JWT + App API Key
    AS-->>GW: user_id, app_id, tier
    GW->>SM: Pre-safety check (injection detection)
    SM-->>GW: PASS / BLOCK

    GW->>WE: Execute workflow
    WE->>WE: Validate inputs schema
    WE->>MR: Route(task_type, tier, app_config)
    MR-->>WE: Selected model

    WE->>PR: Render prompt(slug, inputs)
    PR->>PR: Load from DB/cache → Jinja2 render
    PR-->>WE: (system_prompt, user_prompt)

    WE->>CB: Build context(user_id, session_id)
    CB->>MS: Get long-term memories
    MS-->>CB: Memory facts
    CB-->>WE: Context string

    WE->>AD: Generate(model, prompts, context)
    AD->>AD: Call Ollama / OpenAI API
    AD-->>WE: AdapterResponse

    WE->>WE: Parse output per workflow spec
    WE->>SM: Post-safety check (output moderation)
    SM-->>WE: (sanitized output + disclaimers)

    WE->>LS: Log workflow run (async)
    WE-->>CA: {output, model_used, tokens, latency}
```

---

## 3. Model Routing Flow

```mermaid
flowchart TD
    START([Incoming Request]) --> Q1{Explicit model\npreference set?}

    Q1 -->|Yes| C1[Fetch model by name]
    C1 --> H1{Model active\n& healthy?}
    H1 -->|Yes| USE[Use this model ✓]
    H1 -->|No| Q2

    Q1 -->|No| Q2{App config has\ndefault_model_id?}
    Q2 -->|Yes| C2[Fetch app default model]
    C2 --> H2{Active & healthy?}
    H2 -->|Yes| USE
    H2 -->|No| Q3

    Q2 -->|No| Q3{Workflow has\npreferred_tags?}
    Q3 -->|Yes| C3[Find model by tag\n+ user tier filter]
    C3 --> H3{Found & healthy?}
    H3 -->|Yes| USE
    H3 -->|No| Q4

    Q3 -->|No| Q4{Apply tier-based\nrouting}
    Q4 -->|free| T1[Ollama only]
    Q4 -->|pro| T2[Ollama preferred,\nOpenAI fallback]
    Q4 -->|enterprise| T3[Best model\nfor task]
    T1 --> H4{Healthy?}
    T2 --> H4
    T3 --> H4
    H4 -->|Yes| USE
    H4 -->|No| Q5

    Q5{App fallback\nmodel configured?}
    Q5 -->|Yes| C5[Fetch fallback model]
    C5 --> H5{Active & healthy?}
    H5 -->|Yes| USE
    H5 -->|No| Q6

    Q5 -->|No| Q6{Global platform\ndefault exists?}
    Q6 -->|Yes| C6[Use global default]
    C6 --> USE
    Q6 -->|No| ERR[503 — No model available]

    USE --> LOG[Log routing decision\nto request_logs]
    LOG --> DONE([Proceed to Inference])
```

---

## 4. RAG Pipeline Flow

```mermaid
flowchart LR
    subgraph INGEST["Document Ingestion Pipeline"]
        direction TB
        UP[User uploads document] --> BL[Store to Azure Blob]
        BL --> DB1[Save Document record\nstatus=pending]
        DB1 --> JOB[Celery: embedding_job triggered]
        JOB --> PARSE[Parse document\nPDF/DOCX/TXT]
        PARSE --> CHUNK[TextChunker\nsize=512, overlap=64]
        CHUNK --> EMBD[Embedder\nnomic-embed-text via Ollama]
        EMBD --> STORE[Store chunks + vectors\nin PostgreSQL / Qdrant]
        STORE --> DB2[Update Document\nstatus=indexed]
    end

    subgraph RETRIEVAL["RAG Retrieval at Query Time"]
        direction TB
        Q[User query arrives] --> QE[Embed query\nwith same model]
        QE --> VS[Vector similarity search\npgvector cosine distance]
        VS --> FILTER[Filter by min_score ≥ 0.70\nscoped to user + app]
        FILTER --> TOPK[Return top-K chunks]
        TOPK --> FMT[Format as context block]
        FMT --> INJ[Inject into prompt\nbefore model call]
    end

    INGEST -.->|indexed documents available| RETRIEVAL
```

---

## 5. Prompt Management Flow

```mermaid
stateDiagram-v2
    [*] --> DRAFT : Admin creates prompt

    DRAFT --> DRAFT : Edit template\nAdd/change variables\nUpdate model params

    DRAFT --> PUBLISHED : Admin publishes version N
    note right of PUBLISHED
        Sets is_published = true
        Sets active_version = N
        Previous version → DEPRECATED
    end note

    PUBLISHED --> DEPRECATED : Newer version published

    DEPRECATED --> PUBLISHED : Admin rollback to this version
    note right of DEPRECATED
        Creates new PromptVersion record
        with incremented version number
        pointing to old template content
    end note

    DRAFT --> [*] : Archived (never published)
    DEPRECATED --> [*] : Archived

    state PUBLISHED {
        [*] --> ACTIVE_IN_PROD
        ACTIVE_IN_PROD --> TESTED : Test endpoint called
        TESTED --> ACTIVE_IN_PROD
    }
```

---

## 6. Prompt Resolution Flow (Per-Request)

```mermaid
flowchart TD
    REQ([Request: workflow=quiz_generation\napp_id=eduai]) --> S1

    S1[Look for prompt with\nslug=quiz_generation\napp_id=eduai] --> F1{Found?}

    F1 -->|Yes| S2[Use app-specific prompt\nVersion = active_version]
    F1 -->|No| S3[Look for global prompt\nslug=quiz_generation\napp_id=NULL]

    S3 --> F2{Found?}
    F2 -->|Yes| S4[Use global prompt]
    F2 -->|No| ERR[404 — Prompt not configured]

    S2 --> FETCH[Fetch active PromptVersion from DB]
    S4 --> FETCH

    FETCH --> CACHE{In Redis\ncache?}
    CACHE -->|Hit| RENDER
    CACHE -->|Miss| DB[Load from PostgreSQL\nCache result]
    DB --> RENDER

    RENDER[Jinja2 render with\ninput variables] --> VAL{All required\nvariables present?}
    VAL -->|No| VALERR[400 — Missing variables]
    VAL -->|Yes| TOK[Token count check]
    TOK --> DONE([Return rendered\nsystem + user prompts])
```

---

## 7. User Memory Flow

```mermaid
flowchart TB
    subgraph WRITE["Memory Write Path (after response)"]
        direction LR
        RESP[Model response received] --> BGEX[Background task triggered]
        BGEX --> ANLY[Analyze conversation for\nmemorable facts\nvia LLM extraction prompt]
        ANLY --> EXT{Facts\nextracted?}
        EXT -->|Yes| UPSRT[Upsert to user_memory table\nkey=fact_name, value=fact_value\nsource=inferred]
        EXT -->|No| SKIP[Skip]
    end

    subgraph READ["Memory Read Path (before request)"]
        direction LR
        REQ2[New request arrives] --> MQ[Query user_memory\nWHERE user_id=X\nAND app_id IN X, NULL\nORDER BY last_accessed DESC\nLIMIT 8]
        MQ --> FMT[Format as context block]
        FMT --> INJ2[Inject into system prompt\nas Known facts about user]
    end

    subgraph COMPRESS["Session Summarization"]
        direction LR
        SESS[Session exceeds\n20 messages or 4000 tokens] --> SUMJ[Celery: memory_summarize_job]
        SUMJ --> SUMR[LLM call with\nsummarization prompt]
        SUMR --> SAVS[Save to sessions.context_summary]
        SAVS --> CLRD[Clear Redis session messages\nkeep last 5]
    end

    subgraph TIERS["Memory Tiers"]
        L1["L1: Request-scope context\n(in-flight, RAM only)"]
        L2["L2: Short-term session\n(Redis, TTL 2h)\nLast N messages"]
        L3["L3: App-specific memory\n(PostgreSQL)\nUser prefs per app"]
        L4["L4: Cross-app memory\n(PostgreSQL)\nName, goals, learning style"]
    end

    L4 --> L3 --> L2 --> L1
```

---

## 8. Safety Pipeline Flow

```mermaid
flowchart TD
    INPUT([User Input]) --> ID[Injection Detector\nRegex + pattern matching]
    ID --> ID_PASS{Injection\ndetected?}
    ID_PASS -->|Yes| BLK1[Block request\n400 Bad Request\nLog safety_flag]
    ID_PASS -->|No| TB[Topic Blocker\nCheck app safety policy\nblocked_topics list]
    TB --> TB_PASS{Topic\nblocked?}
    TB_PASS -->|Yes| BLK2[Block request\nor Warn based on policy.action_on_flag]
    TB_PASS -->|No| LEN[Input length check\nmax_tokens validation]
    LEN --> MODEL_CALL[Proceed to\nmodel inference]

    MODEL_CALL --> OUT[Model Output]
    OUT --> MOD[Output Moderator\nHarmful content check]
    MOD --> MOD_PASS{Harmful\ncontent?}
    MOD_PASS -->|Yes, severity=high| BLK3[Block response\nReturn safe fallback message]
    MOD_PASS -->|Yes, severity=low| WARN[Pass with warning header\nX-Safety-Warning: true]
    MOD_PASS -->|No| DISC[Disclaimer Injector\nCheck policy.required_disclaimers]
    DISC --> DISC_PASS{Disclaimer\nrequired?}
    DISC_PASS -->|Yes| INJECT[Append disclaimer text\nto response]
    DISC_PASS -->|No| CLEAN[Output Cleaner\nStrip control chars, normalize]
    INJECT --> CLEAN
    CLEAN --> RESPONSE([Safe Response Delivered])
    BLK1 --> SAFETYLOG[Log to safety_logs table]
    BLK2 --> SAFETYLOG
    BLK3 --> SAFETYLOG
    WARN --> SAFETYLOG
```

---

## 9. Azure Deployment Architecture

```mermaid
graph TB
    subgraph INTERNET["Internet"]
        USR[Client Apps / Mobile / Browser]
    end

    subgraph AZURE_EDGE["Azure Edge"]
        AFD[Azure Front Door\nWAF + SSL + CDN]
    end

    subgraph AZURE_APIM["Azure API Management"]
        APIM[APIM\nRate Limiting\nAPI Analytics\nVersioning]
    end

    subgraph AZURE_VNET["Azure VNet — saib-prod-vnet"]
        subgraph AKS_CLUSTER["AKS Cluster"]
            subgraph NS_PROD["Namespace: saib-prod"]
                API_POD[saib-api pods\n3–20 replicas, HPA]
                WRK_POD[saib-worker pods\nCelery, 2–5 replicas]
            end
            subgraph NS_MON["Namespace: monitoring"]
                PROM[Prometheus]
                GRAF[Grafana]
                JAEG[Jaeger]
            end
        end

        subgraph GPU_VM["GPU VM (NC-series)"]
            OLLM[Ollama\nLocal LLM Server]
        end

        subgraph DATA_SVCS["Managed Data Services"]
            PG_DB[(Azure PostgreSQL\nFlexible Server\nBusiness Critical)]
            REDIS[(Azure Cache\nfor Redis Premium)]
        end
    end

    subgraph AZURE_STORAGE["Azure Storage"]
        BLOB[Azure Blob Storage\nDocuments + Model Artifacts]
        KV[Azure Key Vault\nSecrets + API Keys]
        ACR[Azure Container Registry\nDocker Images]
    end

    subgraph OPENAI_EXT["External Providers"]
        OAI_API[OpenAI API\nFallback Provider]
    end

    subgraph CICD["CI/CD"]
        GHA[GitHub Actions\nCI: test + lint\nCD: build + push + deploy]
    end

    USR --> AFD
    AFD --> APIM
    APIM --> API_POD
    API_POD --> GPU_VM
    API_POD --> PG_DB
    API_POD --> REDIS
    API_POD --> BLOB
    API_POD --> KV
    API_POD --> OAI_API
    WRK_POD --> PG_DB
    WRK_POD --> REDIS
    WRK_POD --> GPU_VM
    API_POD -.-> PROM
    WRK_POD -.-> PROM
    PROM --> GRAF
    GHA --> ACR
    ACR --> AKS_CLUSTER
```

---

## 10. CI/CD Pipeline Flow

```mermaid
flowchart LR
    DEV[Developer pushes\nto feature branch] --> PR[Pull Request opened]
    PR --> CI{GitHub Actions\nCI Workflow}
    CI --> LINT[ruff lint + mypy]
    LINT --> TEST[pytest — unit + integration]
    TEST --> COV{Coverage\n≥ 80%?}
    COV -->|No| FAIL[PR blocked]
    COV -->|Yes| REVIEW[Code Review]
    REVIEW --> MERGE[Merge to main]
    MERGE --> CD[GitHub Actions\nCD Workflow]
    CD --> BUILD[docker build\nmulti-stage]
    BUILD --> PUSH[Push image to\nAzure Container Registry\ntagged with git SHA]
    PUSH --> DEPLOY_DEV[Deploy to DEV\nAzure App Service]
    DEPLOY_DEV --> SMOKE[Smoke tests\nPOST /health]
    SMOKE -->|Pass| DEPLOY_QA[Deploy to QA]
    SMOKE -->|Fail| ROLLBACK[Rollback to\nprevious image]
    DEPLOY_QA --> APPROVAL{Manual\napproval}
    APPROVAL -->|Approved| DEPLOY_PROD[Deploy to PROD\nAKS rolling update]
    APPROVAL -->|Rejected| HOLD[Hold for investigation]
    DEPLOY_PROD --> MONITOR[Monitor dashboards\n15 minutes]
    MONITOR -->|Healthy| DONE([Release complete])
    MONITOR -->|Alerts triggered| RBPROD[AKS rollback\nto previous revision]
```

---

## 11. Multi-App Request Isolation

```mermaid
graph TD
    subgraph APP_A["EduAI (app_id=A)"]
        A_REQ[Quiz Generation Request]
    end
    subgraph APP_B["Health Assistant (app_id=B)"]
        B_REQ[Health Chatbot Request]
    end

    A_REQ --> GW[API Gateway]
    B_REQ --> GW

    GW --> AUTH[Auth: Extract app_id]

    AUTH --> A_CFG[Load AppConfig for A\ndefault_model=llama3.2\nsafety_policy=edu_policy\nrag_enabled=true]
    AUTH --> B_CFG[Load AppConfig for B\ndefault_model=llama3.2\nsafety_policy=health_strict\nrag_enabled=false]

    A_CFG --> A_PROMPT[Load EduAI quiz prompt\nor global quiz prompt]
    B_CFG --> B_PROMPT[Load health_chatbot prompt\nwith medical disclaimer vars]

    A_PROMPT --> A_SAFE[Safety: edu_policy\nno blocked topics for edu\nlow severity threshold]
    B_PROMPT --> B_SAFE[Safety: health_strict policy\nblocked: drug_synthesis\nrequired: medical disclaimer\nhigh sensitivity]

    A_SAFE --> SHARED_MODEL[Shared Ollama Model\nllama3.2]
    B_SAFE --> SHARED_MODEL

    SHARED_MODEL --> A_OUT[EduAI Response\nno disclaimer]
    SHARED_MODEL --> B_OUT[Health Response\n+ medical disclaimer appended]
```

---

## 12. Data Flow — End to End (Chat with Memory + RAG)

```mermaid
sequenceDiagram
    participant U as User
    participant API as SAIB API
    participant MEM as Memory Service
    participant RAG as RAG Retriever
    participant PR as Prompt Renderer
    participant OLL as Ollama

    U->>API: POST /v1/chat\n{session_id, message, workflow_context}

    API->>MEM: get_user_memories(user_id, app_id)
    MEM-->>API: [fact: name=John, goal=AWS cert]

    API->>MEM: get_session_history(session_id, limit=20)
    MEM-->>API: [last 5 messages from Redis]

    API->>RAG: retrieve(query=message, user_id, app_id)
    RAG->>RAG: embed query → cosine search
    RAG-->>API: [relevant document chunks]

    API->>PR: render_prompt(slug=mock_interview_chat, inputs)
    PR-->>API: (system_prompt, user_prompt)

    API->>OLL: chat(model=llama3.2,\nsystem=system_prompt,\ncontext=memories+history+rag,\nuser=message)
    OLL-->>API: response content

    API->>MEM: append_message(session_id, user, content)
    API->>MEM: append_message(session_id, assistant, response)
    API->>MEM: trigger memory_extraction_job (async)

    API-->>U: {response, session_id, tokens_used}
```
