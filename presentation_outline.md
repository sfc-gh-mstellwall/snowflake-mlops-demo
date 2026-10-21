# MLOps That Runs on Snowflake — Standard Presentation Outline

## Presentation contract

- **Audience and format:** customer and technical architecture presentation (30–45 minutes, 18 core slides). Built on the official Snowflake Google Slides template (`17J0RNUWIHSyolEJ4dU6iOfmgyqmuEz-wYb2PI0UAzcU`) combining 14 native template layouts (`COVER-1`, `SAFE-HARBOR`, `AGENDA-1`, `CH-1` chapter dividers, `3COL-I`, `3COL-T`, `2COL-T`, `4COL-I`, `4COL-N`, `THANKS`) with 4 visual architecture diagrams inside official template frames (Slides 5, 8, 12, 15).
- **Outcome:** attendees can explain how to isolate environments, separate pipeline releases from model approvals, orchestrate CI/CD and in-Snowflake training across DCM, the Snowflake CLI, and Code Bundles, and operate batch or online predictions with explicit ownership and rollback.
- **Positioning:** one recommended production path with explicit architectural alternatives rather than a catalogue of equally weighted products.
- **Recommended path:** private Git-backed Workspace → exploratory notebooks → tested Python modules → Python-entrypoint Code Bundle on a compute pool → Pre-Prod pipeline validation via GitHub Actions → approved code release in Prod → scheduled/on-demand Prod candidate creation via Task Graph → evaluation and accountable owner approval → warehouse batch serving (or stable Gateway + disposable SPCS services for online latency) → monitoring and reviewed improvement.
- **Environment default:** separate databases (`ML_DEV`, `ML_PREPROD`, `ML_PROD`) in one Snowflake account. Separate accounts when stronger administrative isolation or data residency requires it; schemas in one database for small sandboxes and learning.
- **Deck links:**
  - **Standard Presentation (18 slides + 45 template toolbox slides):** [MLOps That Runs on Snowflake — Standard Presentation (October 2026)](https://docs.google.com/presentation/d/1QDS-NzGTbERi2C-TlQ4kyTJxYTRkmM6cC4Bvgo08V-g/edit)
  - **Preserved Workshop Master (25 core slides + demo runbooks):** [MLOps That Runs on Snowflake (Workshop Master)](https://docs.google.com/presentation/d/1kzQ48NUvei10eGSe7gbgXzJO61okbe-o2SOyqfH6pTE/edit)

---

## Slide-by-slide plan (18 slides)

| # | Layout | Slide ID | Title | Visual / Content Focus |
|---|---|---|---|---|
| 1 | `COVER-1` | `g3dcdd2133c9_0_2` | `MLOPS THAT RUNS / ON SNOWFLAKE` | Standard Snowflake blue cover (`Repeatable pipelines and governed models`) |
| 2 | `SAFE-HARBOR` | `g3dcdd2133c9_0_18` | `Safe Harbor and Disclaimers` | Fixed official disclaimer slide |
| 3 | `AGENDA-1` | `g3dcdd2133c9_0_27` | `YOUR SESSION ROADMAP` | 1. The Operating Problem · 2. Isolation & Releases · 3. Features & Evidence · 4. CI/CD & Code Bundles · 5. Approval & Operations |
| 4 | `3COL-I` | `g3dcdd2133c9_0_83` | `WHY MODELS FAIL AFTER DEPLOYMENT` | 3 columns w/ icons: `SHIFTING DATA`, `HIDDEN STATE`, `IMPLICIT OWNERS` |
| 5 | `1COL` (Diagram 1) | `g3dcdd2133c9_0_37` | `FOLLOW ONE CONTINUOUS MLOPS LOOP` | Visual diagram: `BUILD & VALIDATE (ML)` (1. Explore, 2. Prepare, 3. Train) → central `4. REVIEW & APPROVE` gate → `SERVE & OPERATE (OPS)` (5. Serve, 6. Monitor, 7. Improve) + feedback loop bar |
| 6 | `CH-1` | `g3dcdd2133c9_0_33` | `ARCHITECTURE / ISOLATION & RELEASES` | Snowflake blue/white colorstack chapter divider |
| 7 | `3COL-T` | `g3dcdd2133c9_0_71` | `CHOOSE THE RIGHT ISOLATION BOUNDARY` | 3 columns: `SCHEMAS IN 1 DB` (simple/sandbox), `SEPARATE DBS` (recommended default), `SEPARATE ACCTS` (strict residency/blast-radius) |
| 8 | `2COL` (Diagram 2) | `g3dcdd2133c9_0_44` | `PROMOTE CODE. GATE EACH MODEL.` | Visual diagram: Top `LOOP 1: PIPELINE RELEASE (GitHub Actions)` rail across `DEV DATABASE`, `PRE-PROD DATABASE` (`GATE 1: PIPELINE DECISION`), and `PROD DATABASE` (`LOOP 2: Train Prod Candidate` → `GATE 2: MODEL APPROVAL` → `Live Incumbent Serving`) |
| 9 | `CH-1` | `SLIDES_API1771097440_4` | `ENGINEERING / FEATURES TO CODE BUNDLES` | Snowflake blue/white colorstack chapter divider |
| 10 | `2COL-T` | `g3dcdd2133c9_0_52` | `REUSE FEATURES AND PIN THE CONTRACT` | 2 columns: `POINT-IN-TIME INTEGRITY` (Feature Store GA spine joins + immutable Dataset GA snapshots) vs. `SHARED VS OWNED FEATURES` (version pinning + release-time deployment) |
| 11 | `4COL-I` | `g3dcdd2133c9_0_98` | `TRACE EVERY CANDIDATE END TO END` | 4 columns w/ icons: `1. FEATURES` → `2. DATASET` → `3. EXPERIMENT` → `4. REGISTRY` (`registration != approval`) |
| 12 | `3COL` (Diagram 3) | `g3dcdd2133c9_0_62` | `ORCHESTRATE WITH CLEAR TOOL BOUNDARIES` | Visual diagram: `GITHUB ACTIONS RUNNER (OIDC + snow CLI only)` driving 3 lanes: `DCM PROJECTS (GA)` (scaffolding), `CODE BUNDLES (GA)` (`train.py` & `deploy_service.py` on compute pools), and `SQL CONTROL PROCEDURES` (`ACTIVATE_SERVING`) |
| 13 | `CH-1` | `SLIDES_API1771097440_0` | `OPERATIONS / APPROVAL, SERVING & DRIFT` | Snowflake blue/white colorstack chapter divider |
| 14 | `4COL-N` | `g3dcdd2133c9_0_116` | `A BETTER SCORE IS NOT APPROVAL` | 4 big numbers: `2` Independent releases, `3` Run states (`accepted`, `rejected`, `failed`), `1` Accountable owner gate (`PROMOTION_DECISION`), `100%` Full-path rollback |
| 15 | `1COL` (Diagram 4) | `SLIDES_API1771097440_8` | `BATCH BY DEFAULT, GATEWAY FOR ONLINE` | Visual diagram: Top lane `WAREHOUSE BATCH INFERENCE (GA)` (`PROMOTION_DECISION` → `SET ALIAS = PRODUCTION` → warehouse scoring → durable output); Bottom lane `STABLE GATEWAY (GA) + DISPOSABLE SPCS SERVICES` (`Traffic Split GA` canary/cutover vs. `Shadow Model Preview` mirrored `v2` + `ACTIVATE_SERVING` / `RECOVER_SERVING`) |
| 16 | `3COL-I` | `SLIDES_API1771097440_15` | `MONITOR SYSTEMS, DATA, AND OUTCOMES` | 3 columns w/ icons: `SYSTEM HEALTH`, `DATA & DRIFT` (Model Version & Gateway Monitors), `TRUE OUTCOMES` (delayed final labels & coverage) |
| 17 | `4COL-I` | `SLIDES_API1771097440_30` | `MAKE OWNERSHIP EXPLICIT ACROSS ROLES` | 4 columns w/ icons: `DATA OWNER`, `DATA SCIENTIST`, `ML ENGINEER`, `MODEL OWNER` |
| 18 | `THANKS` | `g3dcdd2133c9_0_175` | `THANK YOU` | Fixed closing slide |

---

## Section narrative and speaker notes

### Section 1: The Operating Problem (Slides 1–5)

- **Slide 4 (`WHY MODELS FAIL AFTER DEPLOYMENT`):**
  - Deploying a model is the starting line, not the finish line. Even when code stands still, customer behaviour, upstream schemas, and delayed ground-truth outcomes change.
  - Three failure modes dominate early ML deployments: unmonitored data/label shift, hidden notebook state (`pip install` in cells, personal roles, unversioned queries), and implicit ownership (treating a higher holdout metric as automatic permission to replace the live model).
- **Slide 5 (`FOLLOW ONE CONTINUOUS MLOPS LOOP` — Diagram 1):**
  - Frame the seven-stage loop as two halves joined by an explicit central gate: `BUILD & VALIDATE (ML)` (`1. Explore`, `2. Prepare`, `3. Train`) and `SERVE & OPERATE (OPS)` (`5. Serve`, `6. Monitor`, `7. Improve`), separated by `4. Review & Approve`.
  - Emphasise the bottom feedback bar: `7. Improve` can mean retaining the incumbent, repairing an upstream data pipeline, retraining a fresh candidate, rolling back, or retiring the model—and every new candidate still passes through `4. Review & Approve`.

### Section 2: Isolation & Releases (Slides 6–8)

- **Slide 6 (`ARCHITECTURE / ISOLATION & RELEASES`):** Chapter transition.
- **Slide 7 (`CHOOSE THE RIGHT ISOLATION BOUNDARY`):**
  - Compare the three Snowflake isolation patterns using the principle **"same workflow, different environment bindings"**:
    1. **Schemas in one database:** lowest overhead for disposable sandboxes and workshops, but shares database administration.
    2. **Separate databases in one account (`ML_DEV`, `ML_PREPROD`, `ML_PROD`):** recommended production default for most teams—clean deployment, grant, and ownership boundaries without cross-account overhead.
    3. **Separate accounts:** strongest blast-radius and data-residency boundary when required by enterprise policy.
- **Slide 8 (`PROMOTE CODE. GATE EACH MODEL.` — Diagram 2):**
  - Walk through the two distinct loops and two distinct decisions:
    - **Loop 1 (Pipeline release — code):** triggered by a reviewed Git commit. GitHub Actions deploys environment scaffolding and promotes the immutable Code Bundle from `DEV` to `PRE-PROD` (`GATE 1: PIPELINE DECISION`) and into `PROD`.
    - **Loop 2 (Prod candidate — model):** inside `PROD`, a Snowflake Task Graph runs the approved Code Bundle against production-governed data to produce a candidate and evaluation receipt. `GATE 2: MODEL APPROVAL` (`PROMOTION_DECISION`) is required before the live incumbent changes.
  - Note that exact-artefact promotion across environments remains a valid alternative when model transfer is preferred over training in `PROD`.

### Section 3: Features, Evidence & Orchestration (Slides 9–12)

- **Slide 9 (`ENGINEERING / FEATURES TO CODE BUNDLES`):** Chapter transition.
- **Slide 10 (`REUSE FEATURES AND PIN THE CONTRACT`):**
  - **Point-in-time integrity:** use Feature Store (GA) spine timestamps and immutable Dataset (GA) snapshots so training only sees what was knowable at prediction time; fit preprocessors strictly on training splits.
  - **Shared vs. model-owned features:** pin explicit shared Feature View versions rather than `"latest"`, validate schema/grain/freshness before training, and deploy changed model-owned definitions on release rather than recreating shared features on every run.
- **Slide 11 (`TRACE EVERY CANDIDATE END TO END`):**
  - Every candidate has an unbroken four-link evidence chain: pinned Feature View versions (`1. FEATURES`) → immutable Dataset snapshot (`2. DATASET`) → Experiment Tracking run with parameters and holdout metrics (`3. EXPERIMENT`) → versioned Model Registry candidate (`4. REGISTRY`).
  - Reinforce the key invariant: **registration in the Model Registry is traceability, not production approval.**
- **Slide 12 (`ORCHESTRATE WITH CLEAR TOOL BOUNDARIES` — Diagram 3):**
  - Answer the common customer question: *"What runs in GitHub Actions vs. Snowflake, and what belongs in DCM vs. CLI vs. Code Bundles?"*
  - **GitHub Actions runner (`snowflakedb/snowflake-actions@v3` with OIDC):** installs **only `snow` CLI** (never `snowflake-ml-python`) and uses three step types: `snow dcm plan/deploy`, `snow stage copy + snow sql` (to create a release-specific Code Bundle `CREDIT_RISK_TRAINING_<release_id>`), and `snow sql` (for validation and activation).
  - **Three Snowflake execution layers:**
    1. **DCM Projects (GA):** declarative environment scaffolding (schemas, warehouses, stages, roles, grants, control tables, suspended Task Graphs, and owner's-rights SQL procedures).
    2. **Code Bundles (GA):** versioned Python ML execution on compute pools—both `jobs/train.py` (creating Feature Views, Datasets, Experiment runs, and Model versions at runtime) and `jobs/deploy_service.py` (creating and smoke-testing SPCS model services via `snowflake-ml-python` inside Snowflake). Note that `EXECUTE CODE BUNDLE` is caller's-rights only.
    3. **SQL Control Procedures:** `ML_PROD.CONTROL.ACTIVATE_SERVING` (`EXECUTE AS OWNER`, owned by `prod_owner`) verifies `PROMOTION_DECISION` and `SERVICE_DEPLOYMENT` before changing the `PRODUCTION` alias or `ALTER GATEWAY` traffic weights.

### Section 4: Approval, Serving & Monitoring (Slides 13–17)

- **Slide 13 (`OPERATIONS / APPROVAL, SERVING & DRIFT`):** Chapter transition.
- **Slide 14 (`A BETTER SCORE IS NOT APPROVAL`):**
  - Summarise the release and governance numbers:
    - **`2` Independent releases:** Pre-Prod approves the pipeline release; Prod evaluates and approves the trained model.
    - **`3` Run states:** `accepted` (passed deterministic policy checks; eligible for review), `rejected` (incumbent stays live), or `failed` (technical/contract failure).
    - **`1` Accountable owner gate:** `PROMOTION_DECISION` recorded in Snowflake before any serving change is allowed.
    - **`100%` Full-path rollback:** `RECOVER_SERVING` restores the compatible model version, alias or Gateway weights, and feature contract together.
- **Slide 15 (`BATCH BY DEFAULT, GATEWAY FOR ONLINE` — Diagram 4):**
  - **Top lane — Warehouse Batch Inference (GA) (Recommended default):** once `PROMOTION_DECISION` is verified, `ACTIVATE_SERVING` moves the `PRODUCTION` model alias (`ALTER MODEL ... VERSION ... SET ALIAS = PRODUCTION`), scheduled batch scoring runs on a virtual warehouse, and predictions are written with prediction IDs, timestamps, and model version for downstream outcome joins.
  - **Bottom lane — Online Reference Branch (Stable Gateway GA + Disposable SPCS Services):**
    - The **Gateway (`CREATE GATEWAY`)** is created once per environment and owns the permanent URL for callers.
    - **Per-version SPCS services** (`CREDIT_RISK_SVC_V2`, created with `autocapture=True` when online comparison is needed) are disposable compute endpoints created and smoke-tested by `EXECUTE CODE BUNDLE ... ENTRYPOINT = 'jobs/deploy_service.py'`.
    - `CALL ML_PROD.CONTROL.ACTIVATE_SERVING(...)` verifies approval and smoke-test records, runs `ALTER GATEWAY ... FROM SPECIFICATION`, and supports **two online rollout patterns**:
      1. **Traffic Split (`type: traffic_split`, GA):** weighted live routing summing to `100` (e.g., `90/10` canary then `100%` cutover), keeping `v1` warm as the rollback target.
      2. **Shadow Model (`type: shadow_traffic`, Preview):** `primary` (`v1`) continues serving `100%` of caller responses while a configured percentage of live requests is mirrored to `shadow` (`v2`) with zero impact on production callers—ideal for validating live latency, feature distributions, and score agreement via Auto Capture and a Gateway Model Monitor before routing live responses to `v2`.
- **Slide 16 (`MONITOR SYSTEMS, DATA, AND OUTCOMES`):**
  - Separate monitoring into three distinct questions:
    1. **System health:** did tasks, services, and monitors run within latency and capacity budgets?
    2. **Data & drift:** have feature distributions or prediction scores shifted against baseline in Model Version Monitors (GA, source-table based) or Gateway Model Monitors (Preview, comparing challenger/shadow services against `BASE_SERVICE` using Auto Capture logs)? Drift is an investigation trigger, not proof of accuracy loss or an automatic retraining trigger.
    3. **True outcomes:** how did predictions perform once delayed ground-truth labels (e.g., 90-day credit default) matured? Always check join coverage and treat immature/unmatched cohorts as unknown, never as negative outcomes.
- **Slide 17 (`MAKE OWNERSHIP EXPLICIT ACROSS ROLES`):**
  - Close with the four explicit accountabilities: **Data Owner**, **Data Scientist**, **ML Engineer**, and **Model / Production Owner**. One person may hold multiple hats in a smaller team, but no responsibility is left implicit.
  - Closing test: *"Can this model run, fail safely, and recover without its original author?"*
- **Slide 18 (`THANK YOU`):** Q&A and discussion.
