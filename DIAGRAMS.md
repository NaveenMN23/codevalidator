# Platform Diagrams

All diagrams use [Mermaid](https://mermaid.js.org/) syntax — rendered automatically on GitHub, GitLab, and Notion.

---

## 1. High-Level Design (HLD)

> 30,000-foot view of every service, infrastructure component, and the data paths between them.

```mermaid
graph TD
    subgraph Clients
        Admin(["👤 Admin / CI"])
        Candidate(["👤 Candidate"])
    end

    subgraph "Platform Services"
        UI["🖥️ React Web UI\n(Vite + WebContainers)"]
        Backend["☕ Platform Backend\n(Java / Spring Boot 3)"]
        Codegen["🤖 Codegen Service\n(Python / FastAPI)"]
        Workers["⚙️ Grading Workers\n(Python)"]
    end

    subgraph "Infrastructure"
        DB[("🐘 PostgreSQL\n(Relational data)")]
        Redis[("⚡ Redis\n(Cache / Blueprints)")]
        RabbitMQ[["🐰 RabbitMQ\n(Message Broker)"]]
        MinIO[["📦 MinIO / S3\n(Object Storage)"]]
        Docker["🐳 Docker\n(Isolated Sandbox)"]
    end

    subgraph "External APIs"
        OpenAI["OpenAI GPT-4o"]
        Anthropic["Anthropic Claude"]
    end

    Admin -->|"POST /admin/generate-golden-repo"| Codegen
    Candidate -->|"Browser"| UI

    UI -->|"REST / JSON + JWT"| Backend
    UI -->|"Download scaffold ZIPs"| MinIO

    Backend -->|"Users, Problems,\nSubmissions, Blueprints"| DB
    Backend -->|"Draft cache\nBlueprint cache"| Redis
    Backend -->|"grading-queue"| RabbitMQ
    Backend -->|"grading-results-queue"| RabbitMQ

    Codegen -->|"Gold masters + scaffolds"| MinIO
    Codegen -->|"blueprint:{id} direct write"| Redis
    Codegen -->|"blueprint-queue"| RabbitMQ
    Codegen -->|"Generate challenge assets"| OpenAI

    Workers -->|"grading-queue"| RabbitMQ
    Workers -->|"grading-results-queue"| RabbitMQ
    Workers -->|"Run candidate code"| Docker
    Workers -->|"Read blueprint"| Redis
    Workers -->|"AI feedback (premium)"| Anthropic
```

---

## 2. Low-Level Design (LLD)

> Internal component breakdown of each service showing classes, APIs, and data contracts.

```mermaid
graph LR
    subgraph "Platform Backend — Java Spring Boot"
        direction TB
        AuthCtrl["AuthController\n/auth/signup\n/auth/login"]
        ProbCtrl["ProblemController\n/problems\n/problems/:id"]
        UserCtrl["UserController\n/users/me"]

        AuthSvc["AuthService\n• register()\n• login()\n• validateToken()"]
        ProbSvc["ProblemService\n• listProblems()\n• getProblem()\n• saveDraft()\n• submitSolution()"]

        UserRepo["UserRepository"]
        ProbRepo["ProblemRepository"]
        SubRepo["SubmissionRepository"]
        DraftRepo["DraftRepository"]

        BlueprintSvc["BlueprintService\n• saveBlueprint()\n• getBlueprint()"]
        BlueprintRepo["BlueprintRepository"]

        JwtFilter["JwtAuthFilter"]
        SecConfig["SecurityConfig"]

        AuthCtrl --> AuthSvc
        ProbCtrl --> ProbSvc
        UserCtrl --> AuthSvc

        AuthSvc --> UserRepo
        ProbSvc --> ProbRepo
        ProbSvc --> SubRepo
        ProbSvc --> DraftRepo
        BlueprintSvc --> BlueprintRepo

        JwtFilter --> AuthSvc
        SecConfig --> JwtFilter
    end

    subgraph "Codegen Service — Python FastAPI"
        direction TB
        Route["POST /admin/generate-golden-repo\nGoldenRepoRequest\n• languages: list\n• tiers: list\n• scenarios_per_tier: int"]

        ScaffoldGen["ScaffoldGenerator\n• generate()\nPhase 1 → Phase 2a → Phase 2b"]
        DesignPhase["Phase 1\ndesign_challenge.mdx\n→ DesignOutput"]
        SkeletonPhase["Phase 2a\nimplement_skeleton_{lang}.mdx\n→ SkeletonOutput"]
        DeltaPhase["Phase 2b\nimplement/debug_function_{lang}.mdx\n→ FunctionDeltaOutput"]

        Engine["ChallengeGenerator\n• generate_from_dict()\n• _build_readme()"]
        StorageClient["StorageClient\n• upload_gold_master_from_dict()\n• export_scaffold_locally()"]
        BlueprintSvcPy["BlueprintService\n• generate_all_scenarios()\n• dispatch()"]
        QueuePub["QueuePublisher\n• publish(blueprint-queue)"]
        CacheClient["CacheClient\n• set(blueprint:{id})"]
        Validators["Validators\nDesignOutput\nSkeletonOutput\nFunctionDeltaOutput"]
        Sanitizer["Sanitizer\n• sanitize_description()\n• sanitize_generated_files()"]
        LLMClient["LLMClient\n• complete_json()\n• complete_json_cached()\n• load_prompt()"]

        Route --> ScaffoldGen
        ScaffoldGen --> DesignPhase
        ScaffoldGen --> SkeletonPhase
        ScaffoldGen --> DeltaPhase
        DesignPhase --> Validators
        SkeletonPhase --> Validators
        DeltaPhase --> Validators
        ScaffoldGen --> Engine
        ScaffoldGen --> StorageClient
        ScaffoldGen --> BlueprintSvcPy
        BlueprintSvcPy --> QueuePub
        BlueprintSvcPy --> CacheClient
        ScaffoldGen --> LLMClient
        ScaffoldGen --> Sanitizer
    end

    subgraph "Grading Workers — Python"
        direction TB
        Consumer["GradingConsumer\n• _process_job()\nListens: grading-queue"]
        DockerExec["DockerExecutor\n• execute()\nIsolated, no network"]
        LLMEval["LLMEvaluator\n• evaluate() (premium)\nClaude Haiku"]
        ResultPub["ResultPublisher\n• publish(grading-results-queue)"]

        Consumer --> DockerExec
        Consumer --> LLMEval
        Consumer --> ResultPub
    end

    subgraph "React UI"
        direction TB
        IDE["CodeForge IDE\n• Split pane editor\n• WebContainers (WASM)"]
        ProbView["Problem View\n• Markdown renderer\n• Scaffold loader"]
        FeedbackView["Feedback Panel\n• AI eval results\n• Interviewer follow-up"]
        APILayer["API Layer\n• authApi\n• problemApi\n• submissionApi"]

        IDE --> APILayer
        ProbView --> APILayer
        FeedbackView --> APILayer
    end
```

---

## 3. Entity Relationship Diagram (ERD)

> Database schema across PostgreSQL tables (Flyway-managed).

```mermaid
erDiagram
    users {
        UUID id PK
        VARCHAR email UK
        VARCHAR password_hash
        VARCHAR auth_provider
        VARCHAR provider_id
        VARCHAR display_name
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    problems {
        UUID id PK
        VARCHAR slug UK
        VARCHAR title
        TEXT description
        VARCHAR difficulty
        VARCHAR problem_link
        TEXT_ARRAY tags
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    user_problem {
        UUID user_id FK
        UUID problem_id FK
        VARCHAR status
        NUMERIC best_score
        INTEGER attempt_count
        TIMESTAMPTZ last_attempted_at
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    submissions {
        UUID id PK
        UUID user_id FK
        UUID problem_id FK
        VARCHAR submission_link
        NUMERIC score
        TIMESTAMPTZ submitted_at
        TIMESTAMPTZ created_at
    }

    drafts {
        UUID user_id FK
        UUID problem_id FK
        VARCHAR draft_link
        TIMESTAMPTZ updated_at
    }

    blueprints {
        VARCHAR challenge_id PK
        JSONB blueprint_json
        TIMESTAMPTZ created_at
    }

    users ||--o{ user_problem    : "tracks progress"
    problems ||--o{ user_problem : "tracked by"
    users ||--o{ submissions     : "submits"
    problems ||--o{ submissions  : "receives"
    users ||--o{ drafts          : "saves"
    problems ||--o{ drafts       : "drafted for"
    problems ||--o| blueprints   : "evaluated by"
```

**Redis keys (non-relational):**

| Key Pattern | Value | TTL | Written by |
|---|---|---|---|
| `blueprint:{challengeId}` | Blueprint JSON | 1 year (codegen) / 7 days (backend) | Codegen direct write |
| `draft:{userId}:{problemId}` | Draft file map | Session | Backend |
| `semantic:{hash}` | LLM response | 24h | Workers |

---

## 4. Flow Diagram

### 4a — Challenge Generation Flow (Admin)

```mermaid
flowchart TD
    A([Admin sends POST /admin/generate-golden-repo]) --> B[Sanitize prompt]
    B --> C{Valid?}
    C -- No --> ERR1([HTTP 400 Bad Request])
    C -- Yes --> D

    D["Phase 1: design_challenge.mdx\nGPT-4o → DesignOutput\nOne design per tier × N scenarios"]
    D --> E{Validates?}
    E -- No, retry --> D
    E -- Yes --> F

    F["For each language in languages list"]
    F --> G

    subgraph "Phase 2a — Skeleton (per tier)"
        G["implement_skeleton_{lang}.mdx\nGPT-4o → SkeletonOutput\nFull codebase + stubs + per-scenario READMEs"]
        G --> H{Validates?}
        H -- No, retry → correction prompt --> G
        H -- Yes --> I[Store SkeletonOutput for tier]
    end

    I --> J

    subgraph "Phase 2b — Deltas (per scenario)"
        J["implement/debug_function_{lang}.mdx\nGPT-4o → FunctionDeltaOutput\nCorrect body + hidden test"]
        J --> K{Validates?}
        K -- No, retry --> J
        K -- Yes --> L[Store delta + test]
    end

    L --> M

    subgraph "Assembly + Upload"
        M["Inject all deltas → Gold Master\nSanitize files"]
        M --> N[Upload gold-masters/{lang}/{name}-{tier}.zip → MinIO private]
        M --> O[Generate scaffold ZIP per scenario\nstubs → TODO comments\nAdd scenario README]
        O --> P[Upload challenges/{lang}/{name}-{scenario}.zip → MinIO public]
        O --> Q[Export to /generated/{name}/{lang}/ — dev only]
    end

    P --> R

    subgraph "Phase 3 — Blueprints"
        R["generate_blueprint.mdx\nGPT-4o → Blueprint JSON\n+ embed goldMasterSource"]
        R --> S[Write blueprint:{id} → Redis\ndirect, unconditional]
        R --> T[Publish → RabbitMQ blueprint-queue\ndurable, survives backend restart]
    end

    S --> U([Return manifest + usage stats])
    T --> U
```

### 4b — Candidate Submission Flow

```mermaid
flowchart TD
    A([Candidate opens challenge]) --> B[UI fetches problem metadata\nfrom Backend]
    B --> C[Download scaffold ZIP\nfrom MinIO challenges/]
    C --> D[Unzip + mount into WebContainer\nWASM Node.js / Python / Java]
    D --> E[Candidate writes code in browser IDE]
    E --> F{Auto-save every 2s}
    F --> G[POST draft to Backend\nRedis + Postgres]
    G --> E

    E --> H([Candidate clicks Submit])
    H --> I[UI sends file map to Backend]
    I --> J[Backend fetches Blueprint\nfrom Redis blueprint:{id}]
    J --> K[Backend dispatches GradingJob\n→ RabbitMQ grading-queue]
    K --> L[Worker consumes GradingJob]

    L --> M[Docker Executor\nMount files into isolated container\nRun hidden tests]
    M --> N{Tests pass?}
    N -- Fail --> O[Score = 0–49\nReturn test output]
    N -- Pass --> P[Score = 50–100\nReturn test output]

    P --> Q{isPremium?}
    O --> Q

    Q -- No --> R[Publish GradingResult → grading-results-queue]
    Q -- Yes --> S[LLM Evaluator\nRead Blueprint from Redis\nCheck semantic cache]
    S --> T[Call Claude Haiku\nLayer 1: Correctness\nLayer 2: Efficiency\nLayer 3: Interviewer Follow-up]
    T --> R

    R --> U[Backend consumes result\nUpdate submission + user_problem]
    U --> V[Push result to UI via polling/WS]
    V --> W([Show score + AI feedback])
```

---

## 5. Swim Lane Diagram

### 5a — Challenge Generation (Admin → Codegen → Infrastructure)

```mermaid
sequenceDiagram
    participant Admin
    participant Codegen as Codegen Service
    participant OpenAI
    participant MinIO
    participant Redis
    participant RabbitMQ

    Admin->>Codegen: POST /admin/generate-golden-repo<br/>{prompt, languages, tiers, scenarios_per_tier}
    Codegen->>Codegen: Sanitize + validate request

    Note over Codegen,OpenAI: Phase 1 — Design (once)
    Codegen->>OpenAI: design_challenge.mdx + prompt
    OpenAI-->>Codegen: DesignOutput (tiers × scenarios)
    Codegen->>Codegen: Validate DesignOutput (retry on failure)

    loop For each language
        Note over Codegen,OpenAI: Phase 2a — Skeleton (per tier)
        Codegen->>OpenAI: implement_skeleton_{lang}.mdx + design
        OpenAI-->>Codegen: SkeletonOutput (files + stub_locations)

        Note over Codegen,OpenAI: Phase 2b — Deltas (per scenario)
        Codegen->>OpenAI: implement/debug_function_{lang}.mdx
        OpenAI-->>Codegen: FunctionDeltaOutput (body + hidden test)

        Note over Codegen,MinIO: Upload
        Codegen->>MinIO: PUT gold-masters/{lang}/{name}-{tier}.zip (private)
        Codegen->>MinIO: PUT challenges/{lang}/{name}-{scenario}.zip (public)

        Note over Codegen,Redis: Blueprint dispatch
        loop For each scenario
            Codegen->>OpenAI: generate_blueprint.mdx + scenario
            OpenAI-->>Codegen: Blueprint JSON
            Codegen->>Redis: SET blueprint:{problemId} (1-year TTL)
            Codegen->>RabbitMQ: Publish blueprint-queue (durable)
        end
    end

    Codegen-->>Admin: {challenge, languages, manifests, usage}
```

### 5b — Candidate Submission (UI → Backend → Workers)

```mermaid
sequenceDiagram
    participant UI as React UI
    participant WebC as WebContainer (WASM)
    participant Backend as Platform Backend
    participant RabbitMQ
    participant Worker as Grading Worker
    participant Docker
    participant Redis
    participant Claude as Claude Haiku

    UI->>Backend: GET /problems/:id (JWT auth)
    Backend-->>UI: Problem metadata + scaffold link

    UI->>MinIO: GET challenges/{lang}/{name}-{scenario}.zip
    MinIO-->>UI: Scaffold ZIP

    UI->>WebC: Mount ZIP → WASM Node.js / Python / Java
    WebC-->>UI: Container ready

    Note over UI,Backend: Auto-save loop (every 2s)
    UI->>Backend: PUT /drafts/{problemId} {files}
    Backend->>Redis: SET draft:{userId}:{problemId}
    Backend->>PostgreSQL: UPSERT drafts

    UI->>Backend: POST /submissions/{problemId} {files}
    Backend->>Redis: GET blueprint:{problemId}
    Redis-->>Backend: Blueprint JSON

    Backend->>RabbitMQ: Publish grading-queue<br/>{submissionId, files, isPremium, blueprint}
    Backend-->>UI: 202 Accepted {submissionId}

    RabbitMQ->>Worker: Consume GradingJob

    Worker->>Docker: Run hidden tests in isolated container
    Docker-->>Worker: Test results + exit code

    alt Premium user
        Worker->>Redis: GET blueprint:{problemId}
        Redis-->>Worker: Blueprint JSON
        Worker->>Redis: GET semantic:{codeHash}
        alt Cache miss
            Worker->>Claude: Evaluate code (3-layer analysis)
            Claude-->>Worker: Structured AI feedback
            Worker->>Redis: SET semantic:{codeHash}
        end
    end

    Worker->>RabbitMQ: Publish grading-results-queue<br/>{submissionId, score, output, aiFeedback}
    RabbitMQ->>Backend: Consume GradingResult
    Backend->>PostgreSQL: UPDATE submissions SET score, UPDATE user_problem SET best_score/status
    Backend-->>UI: GradingResult (polling / WebSocket)
    UI-->>Candidate: Score + AI Feedback panel
```

### 5c — Blueprint Persistence (Codegen → Backend, async)

```mermaid
sequenceDiagram
    participant Codegen as Codegen Service
    participant Redis
    participant RabbitMQ
    participant Backend as Platform Backend
    participant PostgreSQL

    Note over Codegen,Redis: Critical path — always succeeds
    Codegen->>Redis: SET blueprint:{id} (expires 1 year)
    Redis-->>Codegen: OK

    Note over Codegen,RabbitMQ: Durable path — survives backend downtime
    Codegen->>RabbitMQ: Publish blueprint-queue (delivery_mode=2)
    RabbitMQ-->>Codegen: Ack

    Note over RabbitMQ,Backend: Backend may be down — messages wait in queue
    RabbitMQ->>Backend: Deliver blueprint message (when backend ready)
    Backend->>PostgreSQL: INSERT INTO blueprints (challenge_id, blueprint_json)
    Backend->>Redis: SET blueprint:{id} (7-day TTL, overwrites)
    Backend-->>RabbitMQ: Ack

    alt Backend fails 3 times
        RabbitMQ->>RabbitMQ: Route to blueprint.dead-letter queue
        Note over RabbitMQ: DLQ — manual inspection
    end
```
