# MLOps with Snowflake — Presentation Outline

## Presentation contract

- **Audience and format:** mixed technical audience; 90-minute, demo-led workshop; no participant labs. Keep 25 core slides, with detailed comparisons and implementation references skipped in the appendix.
- **Outcome:** participants can explain how to release a repeatable training workflow, approve a model separately, and operate predictions with evidence, ownership and recovery.
- **Positioning:** one recommended path, with explicit exceptions rather than a catalogue of equally weighted products.
- **Recommended path:** private Git-backed Workspace → exploratory notebooks → tested Python modules → Python-entrypoint Code Bundle on a compute pool → Pre-Prod pipeline validation → approved code release in Prod → new Prod candidate → evaluation and approval → batch serving → monitoring and reviewed improvement.
- **Environment default:** separate databases in one account, subject to organisational policy. Separate accounts when stronger administrative isolation or data locality requires it. The current disposable demo uses schemas; this is a teaching simplification, not the recommended production topology.
- **Training-location default:** train candidates against production-governed data using approved code. Candidate creation is separate from the live serving path. Preserve exact-artefact promotion as a valid alternative when transfer is allowed and preserving tested identity is preferable.
- **Scope boundary:** this outline describes the target operating model. It does not claim the repository already implements every stage or that any demonstration has run successfully.
- **Existing master:** update [MLOps That Runs on Snowflake](https://docs.google.com/presentation/d/1kzQ48NUvei10eGSe7gbgXzJO61okbe-o2SOyqfH6pTE/edit) in place. Retain its lifecycle, evidence, rejection/rollback, monitoring and ownership material.

Use a compact **Environment impact** callout at stage boundaries. The language is **same workflow, different bindings**, not “no difference”. Detailed matrices belong in the appendix; speaker notes carry implementation qualifications.

Product status is capability-specific. Documentation reviewed 1 October 2026; target-account availability and runtime remain rehearsal checks.

## 1. Establish the operating problem

### 1.1 MLOps makes models operable

- People, engineering practices and platform capabilities take models into production and keep them useful, reproducible and recoverable.
- Unchanged code can face changing data, outcomes and operating conditions. Successful deployment is not the finish line.
- Governance, ownership, testing, source control, cost and automation span the complete lifecycle.

### 1.2 Begin with the decision

- Define who acts, the prediction horizon, costs of false positives/negatives, exclusions, authoritative outcome and delivery requirement.
- Connect model metrics to an operational success measure and a baseline, before choosing an algorithm.
- The synthetic credit-risk example estimates 90-day default risk for portfolio monitoring and case prioritisation. It is not an automated credit-approval or adverse-action system.
- Real credit use needs independent model-risk review, fairness assessment and applicable controls beyond this teaching asset.

### 1.3 Navigate one continuous loop

Explore → prepare → train → review → serve → monitor → improve.

Improvement can mean retaining, repairing, retraining, rolling back or retiring. Feedback may return to any earlier stage. The diagram is an operating model, not a promise that every arrow is automatically captured as platform lineage.

## 2. Make the minimum architecture decisions

Show the recommendation early, then explain its consequences through the lifecycle. Keep full pros/cons in reference slides.

### 2.1 Choose an environment boundary

| Boundary | Advantage | Tradeoff | Choose when |
|---|---|---|---|
| Schemas in one database | Small operational footprint; convenient disposable demo | Shared database administration; isolation still depends on roles and grants | Learning, small teams, intentionally simple deployments |
| **Separate databases, one account** | Clear deployment and ownership boundaries | Account-level administration, compute and limits still need explicit separation | **Workshop production default** |
| Separate accounts | Stronger administrative boundary and locality controls | Per-account deployment, identity, data access and operations | Policy requires stronger isolation |

- Within Dev, use private Git-backed Workspaces and per-developer object namespaces where needed. Collaborate through branches and pull requests, not a shared Git-backed Workspace.
- Names and database boundaries alone do not establish least privilege. Treat development, deployment, candidate creation, live serving and approval as distinct responsibilities.
- Reading or cloning production data into Dev requires an approved data-access policy; cloning is not anonymisation.

### 2.2 Two releases, two decisions

**Pipeline release:** promote the same reviewed source release, dependency policy and tests into each environment, with controlled environment-specific configuration. Record the source commit, release identifier, effective Code Bundle identity and configuration. Do not rebuild from a developer's live Workspace.

**Model release:** a pipeline run produces a candidate and evidence. A separate decision authorises changing the live model. A new code release need not change the model, and a new model can come from unchanged code.

| Strategy | What moves | What must be proved in Prod |
|---|---|---|
| **Promote code; train in Prod** | Approved source/runtime contract; owned feature definitions; pinned shared-feature references | Fresh evaluation of the newly trained candidate; exact-candidate inference checks; approval and rollback readiness |
| Promote a validated artefact | Exact model artefact plus compatible feature/inference contract and evidence | Artefact identity, dependency resolution, permissions, serving compatibility and rollback |

For the default path, Pre-Prod validates the **pipeline and serving contracts** using suitable approved data. It cannot approve the exact model that will be trained later in Prod. Keep the incumbent live while the new Prod candidate is evaluated in a controlled candidate path.

Model sharing, replication and copying are different arrangements, not interchangeable promotion verbs. Shared consumption does not automatically create an independently managed production model. Cross-account deployment and ownership need an explicit design.

### 2.3 Authoring, packaging and compute are separate choices

- **Authoring:** Notebooks and Python files in Workspaces (GA); Remote Development with the Snowflake VS Code extension (Public Preview); or an established local IDE workflow.
- **Packaging:** recommend a Python-entrypoint Code Bundle containing tested modules. A maintained notebook-entrypoint Code Bundle is also valid; notebook entrypoints require compute pools. ML Jobs remains a supported alternative for established or specialised job workflows.
- **Compute:** recommend compute pools for Python-heavy training. Warehouse Code Bundles (Public Preview) suit SQL/Snowpark-heavy processing; warehouse size does not automatically parallelise arbitrary Python. Training compute and inference compute are independent decisions.
- **Notebook discipline:** remove hidden state, parameterise inputs, run from a clean session and test modules independently. Notebook format itself does not prevent versioning or testing.

Remote Development can mount Workspace files and use the Snowflake kernel. Standard Git on a persistent remote drive is a separate workflow from Workspace Git integration; do not promise they are the same repository state.

## 3. Follow the lifecycle with explicit contracts

Each stage answers: **decision → recommended path → evidence/exit criterion → environment impact**. Detailed alternatives and API examples are references, not mandatory detours.

### 3.1 Explore: establish trustworthy inputs and outcomes

- Inspect source grain, keys, coverage, missingness, availability timestamps, late arrivals, exclusions and label finality.
- Record feature hypotheses and a simple baseline; keep held-out outcomes outside exploratory model selection.
- **Environment impact:** use approved Dev inputs. Within an account, controlled reads or copies may suffice; across accounts, deliberately provision approved data through sharing, replication or a prepared extract. Connecting to Prod is a separate execution context, not a cross-account read grant.

### 3.2 Prepare: reuse features without hiding dependencies

- Recreate what was knowable at prediction time. Event time alone may be insufficient when data arrives late or is corrected.
- Use versioned transformations and retained history, or immutable Dataset snapshots, to preserve training/evaluation evidence. A snapshot does not remove leakage.
- Options remain direct tables/views, managed Feature Views and externally maintained Feature Views. Choose ownership and refresh responsibility before choosing a product.

| Feature ownership | Release contains | Dependencies and gates |
|---|---|---|
| Existing shared features | Explicit name/version references and logical-to-physical environment mappings | Owner, compatible schema, entity grain, time semantics, freshness, history and retention |
| New model-specific features | Owned definition code and deployment entrypoint | Source contracts, access, historical coverage, backfill and readiness |
| **Combination** | Owned definitions plus pinned shared references | Both contracts; shared dependencies must be ready before the model pipeline consumes them |

- Release order: confirm shared versions → deploy changed owned definitions → refresh/backfill and validate → freeze training inputs → train → evaluate candidate.
- Deploy definitions when the feature release changes; do not recreate shared features or redeploy everything on every retraining run.
- Missing or incompatible dependencies fail the gate. “Latest” is not a release contract.
- Same feature code helps consistency but does not guarantee parity: validate versions, timestamps, preprocessing, null handling, freshness and serving inputs.
- Consider shared ownership when a second consumer appears; agree the migration and compatibility policy rather than moving ownership implicitly.
- **Environment impact:** bind approved versions to each environment. Cross-account Feature Store sharing and replication are documented; individual Feature Views require their associated metadata/entity tags. Replicating a database includes more than one feature-store schema.
- **Demo 1:** trace prepared feature and Dataset evidence through an Experiment to a candidate; show selected raw-versus-derived evidence rather than spending the slot rebuilding all features.

### 3.3 Train: preserve evidence, then make the workflow repeatable

- Separate training, validation/tuning and final holdout. Fit preprocessing only on training inputs. Compare matching cohorts and label maturity.
- Record feature/Dataset versions, commit, configuration, runtime, seed, parameters, metrics and candidate identity. A seed does not promise bitwise reproducibility.
- Keep model logging inside the relevant active Experiment run. Register a traceable candidate; registration is not approval.

**Workflow inputs:** feature/Dataset references, time window, label definition, evaluation policy, parameters, runtime/dependencies and target environment.

**Workflow outputs:** run ID, model version, metrics, acceptance evidence, release/configuration IDs and durable `accepted`, `rejected` or `failed` status. `accepted` means eligible for the separate promotion decision.

- Extract tested modules and an entrypoint; run unattended on demand before adding a schedule.
- Validate dependency resolution and Registry target platforms separately from the training runtime.
- **Demo 2:** inspect the source/specification, execute a Code Bundle from a Workspace SQL file, then inspect history and durable result. Do not invoke it from a notebook cell.
- **Environment impact:** same workflow, different source mappings, object names, compute, identity and dependencies. Deploy the approved source independently in each account. Record effective bundle/configuration identity rather than assuming local version labels prove equivalence.

### 3.4 Orchestrate and validate the pipeline release

Validate data → freeze Dataset → train/evaluate/log → persist candidate and decision evidence.

- Task Graphs (GA) fit Snowflake-centric orchestration; an established external orchestrator can coordinate the same execution units across systems.
- Pass durable identifiers rather than process memory. Experiment context does not implicitly cross independent tasks or workers.
- Test retries, idempotency, duplicate prevention, concurrency and partial failure. Missing evidence blocks progress.
- Pre-Prod proves data contracts, point-in-time behaviour, runtime and execution identity, inference compatibility, monitor/outcome joins, failure recovery and rollback.
- Deploy schedules suspended. Enable only after on-demand execution and release checks pass.
- Control training/tuning budgets, compute idle behaviour, snapshot retention and monitoring refresh cost.

### 3.5 Review: evaluate the actual candidate and authorise separately

- Evaluate against baseline/incumbent on comparable evidence, including segment support, required fairness/stability, data quality and label maturity.
- Test the exact candidate's signature, dependencies, intended inference path and compatible rollback target.
- Combine deterministic screening with human approval where risk requires it. Record policy version, candidate/incumbent IDs, evidence, decision and accountable approver.
- For the default path, these checks apply to the **new Prod-trained candidate** before the live path changes. This is not unrestricted exploratory training in the serving environment.
- **Demo 3:** reject a candidate without changing the incumbent; approve a different candidate; demonstrate or walk through promotion, verification and full-path rollback.
- **Environment impact:** separate candidate and serving responsibilities in all topologies. Alias/tag-in-place is a lifecycle convention, not schema or database isolation. Artefact-copy promotion belongs to the alternative path.

### 3.6 Serve: choose the smallest path that meets the decision

- **Default:** warehouse batch inference (GA), explicit model resolution, compatible features, prediction IDs/timestamps, durable outputs and an owner.
- **Alternatives:** job-based batch on compute pools for large asynchronous work; online services for a genuine request-time requirement. These introduce additional completion/capacity/availability contracts.
- A Registry alias can steer new batch calls; it does not retarget an existing online service.
- **Online branch:** a Gateway (GA) provides a URL stable for the gateway object's lifetime and traffic splitting between services. Shadow traffic is Public Preview. Do not recreate the gateway as the normal model-upgrade operation.
- Pre-Prod validates the endpoint pattern and integration contract with its own service/gateway. In Prod, deploy the new Prod candidate service, run controlled exact-candidate tests, then authorise traffic changes. Do not route to a Pre-Prod service as a shortcut.
- Gateway-per-environment applies to the online branch only: optional in Dev, production-like in Pre-Prod, stable consumer entrypoint in Prod. Batch-only systems do not need one.
- **Environment impact:** names, output locations, compute, caller permissions and endpoints differ. Cross-account clients select account-specific endpoints and authentication.

### 3.7 Monitor: connect predictions to trustworthy outcomes

- **System:** failures, latency, throughput, pipeline/monitor status and capacity.
- **Data:** schema, freshness, missingness, population and prediction drift.
- **Outcomes:** performance against final labels, segment behaviour, sample sufficiency and business utility.
- Persist prediction ID, time, model version and required feature/score evidence. Join authoritative delayed outcomes with deduplication and finality checks; report match coverage and unmatched/immature cohorts. Unknown is not negative.
- Drift needs representative inputs and a baseline; it does not prove degraded performance. Performance needs sufficiently mature labels.
- Model-version monitors read a named typed source for one model version. Gateway monitors compare online services. Auto Capture supplements operational telemetry; direct-service captures need preparation for a version-monitor source.
- **Environment impact:** test the monitor, label join and alert/action path in Pre-Prod. Meaningful ongoing model-performance monitoring is primarily Prod. Cross-account findings return through an approved evidence/notification path, not unrestricted raw-log copying.
- **Demo 4:** trace one prediction to its outcome, distinguish drift from performance, inspect coverage and choose an operating action.

### 3.8 Improve: investigate before retraining

- Triggers include a scheduled review, enough new final labels, performance degradation, a source/feature change, drift or a business event.
- First distinguish model change from data-pipeline repair. Drift alone does not justify retraining.
- Outcomes: retain, repair, retrain a candidate, roll back or retire. A retrained candidate still passes fresh evaluation and approval.
- Reuse the approved workflow; version changes to features, policy or code explicitly. Apply budgets, owner escalation and retirement/retention rules.
- **Environment impact:** Dev investigates and changes source; Pre-Prod validates the release; Prod runs the approved evaluation/training workflow without automatically replacing the incumbent.

## 4. Ownership and close

- Data owner: source contracts, freshness, history and authoritative final labels.
- Data science: hypotheses, evaluation, candidate evidence and behaviour investigation.
- ML engineering: release packaging, execution, orchestration, telemetry and recovery.
- Production/model owner: risk acceptance, approval, incidents, exceptions and retirement.
- One person may hold several responsibilities; no responsibility should be implicit.
- Revisit the reference architecture and recommendations. End with: **Can this model run, fail safely and recover without its original author?**

## 5. Core deck and timing

Keep the existing 25-slide core. Add environment, early architecture and shared-feature slides; move the detailed feature-pipeline, compute and artefact-versus-code comparisons to the appendix. Preserve their content rather than discard it.

| Slide | Title | Treatment |
|---|---|---|
| 1 | MLOPS THAT RUNS ON SNOWFLAKE | Existing cover; update facilitator runbook |
| 2 | Safe Harbor and Disclaimers | Preserve official text |
| 3 | MLOPS MAKES MODELS OPERABLE | Retain |
| 4 | CODE CAN STAND STILL. DATA CANNOT. | Retain |
| 5 | FOLLOW THE MLOPS LOOP | Retain navigation |
| 6 | START WITH THE DECISION | Retain; connect to teaching use case |
| 7 | CHOOSE THE ISOLATION BOUNDARY | New concise three-option comparison |
| 8 | PROMOTE CODE. GATE EACH MODEL. | New early reference architecture |
| 9 | RECREATE THE PREDICTION MOMENT | Retain |
| 10 | REUSE FEATURES, PIN THE CONTRACT | New shared/owned/readiness visual |
| 11 | COMPARE RUNS, PRESERVE EVIDENCE | Retain |
| 12 | DEMO 1: TRACE A CANDIDATE | Evidence-first demo/runbook |
| 13 | PACKAGE CODE, NOT NOTEBOOK STATE | Clarify entrypoint vs packaging; show compute-pool default |
| 14 | DEMO 2: EXECUTE A CODE BUNDLE | On-demand contract and result |
| 15 | ORCHESTRATE DURABLE HANDOFFS | Retain pre-scheduling discipline |
| 16 | TWO RELEASES, TWO DECISIONS | Make Prod candidate evaluation explicit |
| 17 | A BETTER SCORE IS NOT APPROVAL | Retain |
| 18 | DEMO 3: REJECT, PROMOTE, ROLL BACK | Preserve rejection and complete recovery |
| 19 | CHOOSE HOW PREDICTIONS ARRIVE | Batch default; online branch in notes/reference |
| 20 | WATCH SYSTEMS, DATA, AND OUTCOMES | Retain; Pre-Prod test path |
| 21 | DEMO 4: TURN OUTCOMES INTO ACTION | Finality, coverage and action |
| 22 | RETRAIN ONLY WHEN JUSTIFIED | Retain |
| 23 | MAKE OWNERSHIP EXPLICIT | Retain |
| 24 | BUILD ONE OPERABLE MODEL FIRST | Recap default; return to architecture |
| 25 | Thank You | Questions; references skipped |

Timing: opening/decisions (1–8) 17 minutes; features/evidence (9–12) 16 minutes including Demo 1; packaging/orchestration (13–15) 14 minutes including Demo 2; release/review (16–18) 13 minutes including Demo 3; serving/monitoring/improvement (19–22) 15 minutes including Demo 4; ownership/close (23–25) 5 minutes; protected questions and demo contingency 10 minutes. **Total: 90 minutes.**

References: detailed feature-pipeline choice, compute choice, artefact-versus-code promotion, environment bindings, bundle specifications/commands, authoring alternatives, execution units, training scale, Gateway rollout, monitor selection and source references. Keep existing template toolbox slides skipped.

## 6. Demo readiness and rehearsal gate

As of this review, repository increments 1–3 are implemented but awaiting target-account/Workspace execution. Increments 4–9 are planned: extracted modules and Demo 1 handoff, Code Bundle release, Pre-Prod/Prod training, approval and batch serving, delayed-outcome monitoring, then separately authorised rehearsal. Do not label any demo “live verified” without recorded rehearsal evidence. See `docs/demo-runbook.md`.

| Demo | Time within section | Prerequisites and evidence | Current boundary / fallback |
|---|---|---|---|
| 1: Trace a candidate | 6 min | Executed notebooks; feature/Dataset IDs; comparable Experiment runs; linked Registry candidate; lineage access | Assets implemented, runtime pending. Prepared evidence walkthrough only when genuine records exist; otherwise label it a conceptual walkthrough |
| 2: Execute a bundle | 5 min | Extracted modules, specification, approved dependencies/identity, target bundle support, durable result and execution history | Implementation planned. Walk source/spec/contract; never imply the command ran |
| 3: Reject/promote/rollback | 6 min | Incumbent and candidate, persisted gate records, authorised isolated serving path, exact-candidate smoke test and verified recovery | Implementation planned. Walk the state diagram without invented scores or deployment claims |
| 4: Outcomes into action | 5 min | Prediction records, final/pending outcomes, typed monitor source/baseline, coverage and action policy | Implementation planned. Walk the evidence contract without fabricated monitoring charts |

Before presenting: verify account/region/edition, product status, runtime/packages, actual execution identity, feature readiness, all four evidence paths and rollback. Prepare honest fallback material. Never rehearse this disposable workload in Snowhouse. Presentation updates do not authorise deploying or modifying Snowflake resources.

The older papers and demo roadmap use NPO/ML Job terminology and an exact-model-copy path. This outline is the updated workshop recommendation; aligning the implementation roadmap and building later phases is separate work, not an assertion that those assets already exist.

## 7. Capability references

- [Code Bundles](https://docs.snowflake.com/en/developer-guide/code-bundles/code-bundles): compute-pool execution GA; warehouse execution, inline overrides and new clients Public Preview. Availability must be checked at capability level.
- [Code Bundle execution](https://docs.snowflake.com/en/sql-reference/sql/execute-code-bundle): Python and notebook entrypoints; notebooks on compute pools; no nested execution from notebook cells.
- [Bundle specification](https://docs.snowflake.com/en/developer-guide/code-bundles/code-bundle-yml-reference): compute, runtime and dependency configuration.
- [Remote Development](https://docs.snowflake.com/en/user-guide/vscode-ext-remote-development): Public Preview; extension/runtime prerequisites and Workspace mounting.
- [Feature replication and sharing](https://docs.snowflake.com/en/developer-guide/snowflake-ml/feature-store/replication-sharing): whole-store and individual-view arrangements and metadata dependencies.
- [Model management](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/model-management): versions, aliases and same-account copies.
- [Model Registry](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview): dependency/target-platform contracts and sharing/replication.
- [Gateway routing](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/stable-endpoints-api-reference): lifetime-stable URL, traffic split and Preview shadow traffic.
- [Model observability](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/model-observability): version monitoring, baseline and outcome evidence.
- [Monitor source contract](https://docs.snowflake.com/en/sql-reference/sql/create-model-monitor): authoritative task-specific source types.