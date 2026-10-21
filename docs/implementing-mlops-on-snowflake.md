# From Notebook to Production with Snowflake ML

*A practical path from experimentation to repeatable training, controlled promotion, and retraining*

## 1. Starting point and target state

Consider a data scientist developing a churn model in a Notebook in a Git-backed Workspace. The notebook loads data, creates features, trains several candidates, evaluates them, and registers a promising version. The work is valuable, but it is not yet independently operable. Package installation may be interactive, parameters may be embedded in cells, execution may depend on the author's privileges, and the criteria for accepting a new model may exist only in the author's reasoning.

The practical MLOps objective is to turn that experiment into this repeatable flow:

```text
Notebook experiment
        ↓
Repeatable training modules
        ↓
Immutable source release
        ↓
On-demand Code Bundle in DEV
        ↓
Pipeline validation in Pre-Prod
        ↓
Same approved source in PROD
        ↓
New Prod-trained candidate and evidence
        ↓
Separate screening, approval and serving decisions
        ↓
Warehouse batch inference and monitoring
        ↓
Scheduled or triggered evaluation and retraining
```

The first production-oriented artefact is a repeatable training workflow that is testable and executable by someone other than its author. Once validated, the workflow can be operated on demand, on a schedule, or in response to an event. Pre-Prod can approve the pipeline release; it cannot approve a model that has not yet been trained in Prod.

This paper assumes Notebooks in Workspaces and complements *MLOps with Snowflake ML*, which describes the broader lifecycle and platform capabilities.

## 2. Initiate the project

The project should begin with a repository and an agreed operating boundary, rather than an empty notebook. The repository is the source of truth; a Workspace is a development environment; a Code Bundle is the recommended unattended execution unit; and the Registry model version is the trained artefact. An NPO or ML Job remains a supported alternative for teams that already operate those units.

### Initiation options

| Option | Appropriate use | Main consideration |
|---|---|---|
| Blank private Workspace | Learning and short-lived exploration | Structure and source control depend on the individual |
| Private Git-backed Workspace from an existing repository | Source-controlled individual development | Creation is an interactive, per-user Snowsight step |
| Shared Workspace | Teaching or collaborative Snowflake-managed editing | Shared Workspaces cannot be Git-backed |
| Local IDE and repository | Teams with established local tooling | Snowflake connections and runtime compatibility need standardisation |
| Template repository and private Git-backed Workspace | Standard production-oriented development | Requires an organisation-owned template and bootstrap process |

The recommended default is a **template repository, a private Git-backed Workspace for each developer, and CI/CD deployment from an approved commit**. Developers open the repository as a Workspace and perform interactive setup, exploration, testing, and script execution there. They collaborate through branches and pull requests rather than by sharing one Git-backed Workspace.

This model has a deliberate automation boundary. The platform team can provision API integrations, secrets, roles, schemas, stages, warehouses, compute pools, and approved runtime environments. The organisation's Git platform can create a project repository from a template. Each developer then creates a private Git-backed Workspace through **Projects → Workspaces → From Git repository** in Snowsight. Git-backed Workspace creation is not available through `CREATE WORKSPACE`, DCM, or a CLI, and a regular Workspace cannot be created first and connected to Git later ([Git-backed Workspaces](https://docs.snowflake.com/en/user-guide/ui-snowsight/workspaces-git)).

For the companion demonstration repository, the Git-backed Workspace is the interactive execution boundary. The user runs repository Python files with a Workspace notebook service, opens rendered SQL in the Workspace SQL editor, and develops notebooks alongside the same modules and deployment definitions. A local clone is optional and is not part of the demonstration procedure. Python files execute as complete scripts in Workspaces and can import other repository files by relative path ([Python files in Workspaces](https://docs.snowflake.com/en/user-guide/ui-workspaces-python)).

Production deployment should not depend on a developer's private Workspace. After pull-request approval, CI/CD copies the approved repository contents to an internal or temporary stage and creates a release-specific Code Bundle from that immutable payload. An NPO or ML Job can implement the same contract when an organisation already operates those units. This preserves the commit-to-release relationship ([Code Bundles](https://docs.snowflake.com/en/developer-guide/code-bundles/code-bundles); [production NPO workflow](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-workflow-scenarios)).

The resulting bootstrap path is:

```text
Platform foundations + ML repository template
        ↓
Project repository created from template
        ↓
Private Git-backed Workspace created by each developer
        ↓
Feature branch, development, and pull request
        ↓
Approved commit deployed by CI/CD
        ↓
Environment-specific Code Bundle and later Task Graph
```

## 3. Stage 1: Turn the notebook into a repeatable workflow

The notebook remains useful for exploration, visualisation, and explaining decisions. Reusable logic moves into Python modules with explicit inputs and outputs:

```text
load_training_data(config)      → versioned training data
build_features(data, config)    → training features
train_model(features, config)   → candidate model
evaluate_model(model, data)     → metrics and acceptance evidence
register_candidate(model, ...)  → Registry model version
```

A practical Workspace layout is:

```text
churn_ml/
├── README.md
├── project.yaml
├── requirements.txt
├── config/{dev,test,prod}.yaml
├── src/churn/{data,features,training,evaluation,inference}.py
├── tests/{unit,contracts,integration}/
├── scripts/run_training.py
├── scripts/deploy_dag.py
├── notebooks/churn_experiment.ipynb
├── notebooks/train.ipynb
├── deployment/{npo.sql,task_graph.py,grants.sql,monitor.sql}
└── .github/workflows/{validate.yaml,deploy.yaml}
```

`project.yaml` records stable project metadata without storing credentials:

```yaml
project: churn-risk
model_name: CHURN_DETECTOR
entry_point: scripts/run_training.py
owners:
  development_role: ML_CHURN_DEVELOPER
  production_role: ML_CHURN_PROD_OWNER
runtime:
  environment: cre@ml_cpu_py311_v3
targets:
  dev: ML_DEV.CHURN
  test: ML_TEST.CHURN
  prod: ML_PROD.CHURN
```

Environment files contain non-secret references such as object names, feature versions, thresholds, and compute settings. Credentials remain in Snowflake secrets or the CI platform's approved secret store. The first milestone is simple: another team member can open the same repository branch as a private Git-backed Workspace, select the approved runtime, run `scripts/run_training.py --environment dev` from the Workspace Python editor or terminal, and obtain the same class of outputs without editing code.

### Worked bootstrap: churn-risk

1. The project owner requests a new `churn-risk` repository from the organisation's `snowflake-ml-template`.
2. The repository service creates the repository and applies branch protection, required reviewers, CI checks, and ownership metadata.
3. The platform workflow provisions or assigns `ML_DEV.CHURN`, a deployment stage, warehouse, compute pool, approved CRE, and the `ML_CHURN_DEVELOPER` role. TEST and PROD access remain with deployment and production roles.
4. The data scientist opens Snowsight and creates a private Git-backed Workspace from the repository, using the approved Git API integration and authentication method.
5. The data scientist creates a feature branch, uses a platform-provided compute pool or runs the repository's one-time Workspace compute setup, configures a Workspace notebook service, runs repository bootstrap and validation assets, develops in `notebooks/churn_experiment.ipynb`, and moves reusable logic into `src/churn/`.
6. A pull request runs unit tests, configuration validation, data-contract tests against DEV, dependency checks, and a small training smoke test.
7. After approval, CI/CD identifies the merge commit as a release candidate and deploys it to Pre-Prod. The production deployment later uses that same release identifier.

OAuth is a practical choice for interactive Workspace users. Automated pipelines normally use a non-interactive Git and Snowflake authentication method approved by the organisation, with workload identity federation preferred for Snowflake CI authentication.

The CI workflow can implement the release path as these ordered stages:

```yaml
validate:
  - run: unit and configuration tests
  - run: DEV data-contract and training smoke tests
package:
  - record: commit SHA, dependency lock, and release identifier
  - upload: repository snapshot to the TEST release stage
deploy_preprod:
  - create: release-specific Code Bundle
  - run: Pre-Prod pipeline and serving-contract validation
promote_release:
  - require: Pre-Prod pipeline-release approval
  - upload: the same repository snapshot to the PROD release stage
  - deploy: PROD Code Bundle and later Task Graph in suspended state
verify_and_resume:
  - check: effective release, grants, smoke test, monitoring, and rollback
  - resume: production schedule or trigger
```

This is tool-neutral workflow pseudocode. GitHub Actions, GitLab CI, Azure Pipelines, or another approved system can implement the same gates.

### Define the workflow contract

The training workflow should accept configuration rather than hidden notebook state.

**Inputs**

- Source tables, feature-view versions, or Dataset version.
- Training time range and point-in-time rules.
- Label definition and exclusions.
- Hyperparameters and random seeds.
- Runtime and dependency versions.
- Target database, schema, stage, warehouse, and compute pool.

**Outputs**

- Experiment and run identifier.
- Candidate model version.
- Model signature and target platforms.
- Evaluation metrics and threshold result.
- Source-code commit and configuration identifier.
- Lineage and artefact locations.
- Machine-readable `accepted`, `rejected`, or `failed` status. `accepted` means eligible for a later approval decision, not live serving.

The training entry point ties those outputs to one Experiment run. The following examples are illustrative: the `ML_*` objects, roles, CRE, release identifiers, configuration classes, and application functions must be created or implemented for the organisation. The control flow is concrete even though application-specific code is abbreviated:

```python
def run_training(config):
    experiment = ExperimentTracking(session)
    experiment.set_experiment(config.experiment_name)

    with experiment.start_run(config.run_name):
        training_data, tuning_data, held_out_test_data = load_training_data(config)
        model = train_model(training_data, tuning_data, config)
        metrics = evaluate_model(model, held_out_test_data, config)
        decision = passes_thresholds(metrics, config)

        experiment.log_params(config.logged_params)
        experiment.log_metrics(metrics)
        model_version = experiment.log_model(
            model,
            model_name=config.model_name,
            sample_input_data=held_out_test_data.drop(config.label_column),
            target_platforms=["WAREHOUSE", "SNOWPARK_CONTAINER_SERVICES"],
            options={"relax_version": False},
        )

        return {
            "status": "accepted" if decision else "rejected",
            "model_version": model_version.version_name,
            "metrics": metrics,
            "source_commit": config.source_commit,
        }
```

`held_out_test_data` must not influence feature fitting, hyperparameter tuning, candidate selection, or threshold definition. The model version is registered as a traceable candidate regardless of the decision; the returned status controls whether it can enter promotion. The production implementation should persist the result in a release or validation table so later tasks consume durable state rather than Python process memory.

### Control the environment

Pinning `requirements.txt` controls the project environment, but model dependencies must also be recorded when logging the Registry version. Use governed `pip_requirements` or `conda_dependencies`; where exact versions must remain exact, use `options={"relax_version": False}` ([Model Registry](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview)).

For stricter package, operating-system, and security control, Notebooks and ML Jobs can share a **Custom Runtime Environment**. The organisation extends a Snowflake base image, pins and scans it, pushes it to a Snowflake image repository, and registers the digest-verified environment. This makes the development and execution image an approved versioned dependency rather than a sequence of interactive installation commands ([Custom Runtime Images](https://docs.snowflake.com/en/developer-guide/snowflake-ml/custom-runtime-images)).

If warehouse inference is planned, validate warehouse compatibility and set `target_platforms` explicitly during registration. When omitted, Registry logging defaults to SPCS only in Container Runtime and to both warehouse and SPCS elsewhere. Model or dependency constraints can still make a version unsuitable for warehouse execution ([Registry API](https://docs.snowflake.com/en/developer-guide/snowpark-ml/reference/latest/api/registry/snowflake.ml.registry.Registry)).

## 4. Stage 2: Run the workflow on demand in DEV

The team should operate the workflow manually before scheduling it. This proves that it is independent of notebook state and exposes its real runtime, cost, permissions, and failure modes.

There are three practical execution units. The recommended default is a compute-pool **Code Bundle**.

### Code Bundle

A **Code Bundle** packages reviewed Python modules, or a maintained notebook entrypoint, as a named execution unit with an inspectable specification. Compute-pool bundles are generally available. Warehouse bundles remain Preview and are not the recommended training path. Execute the bundle from a SQL file or task, never from a notebook cell ([Code Bundles](https://docs.snowflake.com/en/developer-guide/code-bundles/code-bundles); [EXECUTE CODE BUNDLE](https://docs.snowflake.com/en/sql-reference/sql/execute-code-bundle)).

Prefer a release-specific bundle name bound to an immutable payload. Record the commit, payload digest, specification digest, runtime and the effective executing identity. Local version labels do not prove cross-environment equality.

An on-demand DEV validation can execute the deployed bundle explicitly:

```sql
EXECUTE CODE BUNDLE ML_DEV.CHURN.CHURN_TRAINING_R_2026_09_11_1
  ENTRYPOINT = 'scripts/run_training.py'
  ARGUMENTS = ('--environment', 'dev', '--config', 'config/dev.yaml');
```

### Versioned Notebook Project Object

An approved Workspace snapshot can still be deployed as a versioned **Notebook Project Object** (NPO). This preserves the notebook as the executable entry point while separating deployed content from ongoing edits. It remains valid when a team already operates notebook projects; it is not the workshop default ([NPO scheduling](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-schedule)).

### ML Job

Use an **ML Job** when an organisation already operates job-based training, needs specialised project packaging, or requires a job API rather than a Code Bundle. Use `@remote` for a function, file or directory submission for a project, and `MLJobDefinition` for a reusable payload executed with different parameters ([ML Jobs](https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-jobs/overview)).

Code Bundles, NPOs and ML Jobs can implement the same training contract. Keep data, evaluation, registration and promotion contracts stable if the execution unit later changes.

For a Code Bundle release, CI/CD uploads the approved commit to an immutable stage path. A release-specific bundle name provides an unambiguous binding between the code validated in Pre-Prod and the object later deployed to Prod:

```sql
CREATE CODE BUNDLE ML_PREPROD.CHURN.CHURN_TRAINING_R_2026_09_11_1
  FROM '@ML_PREPROD.CHURN.ML_RELEASES/churn-risk/2026.09.11.1'
  COMMENT = 'churn-risk release 2026.09.11.1';
```

The release pipeline records the commit SHA, release identifier, stage path, payload digest and bundle name together. File upload is performed by CI with the Snowflake CLI (`snow stage copy`) before this SQL runs through `snow sql`. DCM can alternatively manage a bundle with `DEFINE CODE BUNDLE` (Preview); Section 11 explains why this guide keeps CLI-created release bundles as the default.

### DEV exit criteria

- A second user or service identity can run the workflow.
- Inputs and outputs are explicit and versioned.
- Unit and data-contract tests run outside exploratory cells.
- The run records metrics and configuration in an Experiment.
- `exp.log_model()` registers the candidate during the active run, creating the Experiment-to-model lineage relationship.
- Failure returns a clear status and does not leave a candidate that appears approved.
- Runtime, cost, logs, and artefact locations are known.

## 5. Stage 3: Build the training pipeline

Once the on-demand workflow is reliable, split it into pipeline steps with clear retry and ownership boundaries:

```text
Validate source data
        ↓
Create or select training Dataset
        ↓
Train candidate and evaluate it
        ↓
Log metrics and register candidate in the active Experiment run
        ↓
Publish validation result
```

A **Snowflake Task Graph** can coordinate these steps. Warehouse tasks can handle SQL validation and transformation, while an ML Job can own the active Experiment run, training, evaluation, metric logging, and `exp.log_model()` before completing the run. Active Experiment context does not pass implicitly between independently executing tasks. If training and evaluation are split across jobs, pass durable Dataset, model-artefact, metric, configuration, and run identifiers; open the relevant Experiment/run context explicitly in the task that logs the model ([Task Graphs](https://docs.snowflake.com/en/developer-guide/snowflake-python-api/snowflake-python-managing-tasks); [Experiments](https://docs.snowflake.com/en/developer-guide/snowflake-ml/experiments)). An existing Airflow, Dagster, or Prefect platform can orchestrate the same Snowflake execution units instead.

Deploying the graph does not itself prove that the pipeline runs. Release verification should confirm:

- The graph is resumed or explicitly triggered.
- Its owner has every runtime privilege.
- Reruns are idempotent and do not duplicate model versions or outputs.
- Partial failure and retry preserve the correct Dataset, configuration, and Experiment run.
- A failed evaluation cannot advance to promotion.
- The return value clearly distinguishes trained, rejected, and failed candidates.

During development and Pre-Prod, the Task Graph can run on demand. Production scheduling or event triggers are introduced after the graph is validated and the retraining policy is approved.

For a Code Bundle starting point, the scheduling fragment is explicit about the release-specific bundle and runtime configuration. It assumes the bundle, warehouse, compute pool, task-owner grants, monitoring, and failure notification have already passed Pre-Prod. CI substitutes the approved release identifier before executing the deployment SQL:

```sql
CREATE OR REPLACE TASK ML_PROD.CHURN.CHURN_TRAINING_TASK
  WAREHOUSE = ML_PROD_WH
  SCHEDULE = 'USING CRON 0 4 * * SUN Europe/Stockholm'
AS
  EXECUTE CODE BUNDLE ML_PROD.CHURN.CHURN_TRAINING_R_2026_09_11_1
    ENTRYPOINT = 'scripts/run_training.py'
    ARGUMENTS = ('--environment', 'prod', '--config', 'config/prod.yaml');

-- Resume only after deployment checks confirm the release and grants.
ALTER TASK ML_PROD.CHURN.CHURN_TRAINING_TASK RESUME;
```

In a DCM-managed environment, the task or graph is a `DEFINE TASK` in the environment's DCM project. Newly deployed tasks are suspended by default, so the CI step that resumes the graph remains a separate, verified action. For a multi-step graph, the release process deploys the graph definition instead. The task-owner role receives the minimum privileges needed by every step and is tested in Pre-Prod before the PROD graph is resumed.

## 6. Stage 4: Validate the pipeline release in Pre-Prod

The pipeline release moves through environments with an immutable release identifier. Model promotion remains a separate decision in Stage 5.

| Environment | Purpose | Expected outcome |
|---|---|---|
| DEV | Fast iteration and on-demand execution | Reproducible workflow and candidate evidence |
| Pre-Prod | Production-like data contracts, dependencies, privileges, and failure testing | Pipeline-release decision only |
| PROD | Governed execution, new candidate training, controlled approval, inference, and monitoring | Operated model with accountable owner |

Separate databases are a useful starting point; separate accounts can provide stronger isolation where governance, resilience, or data locality requires it.

Two independent things move through these environments:

**Pipeline release.** Promote one version-controlled commit or release containing the Python package, Code Bundle specification, Task Graph definition, tests, dependency policy, and deployment definitions. Deploy that same release separately into DEV, Pre-Prod, and PROD with environment-specific object names, configuration, ownership, and grants. Pre-Prod approves the pipeline release; it cannot approve a model that Prod has not yet trained. PROD deployment does not rebuild the release from an untracked Workspace state.

**Candidate model.** A pipeline run produces a model candidate and its evidence. Candidate promotion follows the quality and approval process in Stage 5 and remains separate from deployment of the training pipeline. A new pipeline release does not automatically replace the production model, and a newly approved model does not necessarily require a new pipeline release.

### What Pre-Prod should prove

- Source, feature, label, and prediction schemas match the production contract.
- Point-in-time feature generation does not leak future information.
- Runtime images and Registry dependencies resolve without interactive installation.
- The effective execution identity has required privileges and no unnecessary access.
- Training is reproducible within an agreed tolerance.
- The model signature and selected target platforms support the intended inference path.
- Monitoring tables, correlation keys, and delayed ground-truth joins work.
- Rollback restores the previous model and compatible feature/inference path.

## 7. Stage 5: Decide and execute model promotion

A successfully completed training pipeline produces a **candidate**. Replacement of the production model is a separate controlled decision.

Promotion should evaluate:

- Data-quality and volume gates.
- Baseline and incumbent comparison.
- Segment-level thresholds.
- Stability and fairness criteria required by the use case.
- Signature, feature, and dependency compatibility.
- Approval by the accountable model or risk owner.
- Availability of a tested rollback target.

Low-risk use cases can encode deterministic automatic gates. Higher-risk models should retain human approval. In both cases, the decision and evidence should be recorded.

A gate can express the decision independently of the training job:

```python
def decide_promotion(candidate, incumbent, policy):
    checks = {
        "minimum_quality": candidate.auc >= policy.minimum_auc,
        "incumbent_delta": candidate.auc - incumbent.auc >= policy.minimum_delta,
        "segment_floor": min(candidate.segment_auc.values()) >= policy.segment_floor,
        "data_contract": candidate.data_contract_passed,
        "inference_smoke_test": candidate.inference_test_passed,
        "rollback_ready": incumbent.is_deployable,
    }
    return {
        "decision": "approve" if all(checks.values()) else "reject",
        "checks": checks,
        "candidate_version": candidate.version,
        "incumbent_version": incumbent.version,
    }
```

The gate result is stored with the candidate model and release evidence. An approved result authorises a separate deployment action; it does not change an alias or Gateway by itself.

### Build once or retrain in the target environment

Two strategies are valid.

**Build once and promote the validated artefact.** Train and approve an immutable model version in a controlled environment, then copy or register that exact artefact in production. This preserves the identity of what was tested. Same-account copying can use `CREATE MODEL ... FROM MODEL`; cross-account sharing provides consumption rather than an independently managed copy.

**Retrain per environment and revalidate.** Promote code and immutable configuration, train against production-governed data, and treat the output as a new artefact requiring fresh evaluation and approval. This approach can support data-locality and lineage requirements while producing a model version specific to the target environment.

Choose deliberately based on data locality, training cost, reproducibility, regulation, and evidence requirements.

For warehouse inference, a Registry alias can control which version a SQL or Python call resolves. For real-time inference, an alias does not retarget an existing service. Deploy separate champion and challenger services and use a **Gateway** to move traffic. Shadow traffic can copy representative requests to the challenger while callers receive only the primary response; weighted routing can then introduce challenger responses gradually ([Gateways](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/stable-endpoints-api-reference)).

For the online branch, treat the **Gateway as stable** and **services as disposable**:

1. Create one Gateway per environment through the infrastructure workflow. Its hostname is fixed for the lifetime of the gateway object, so it is not recreated during a model upgrade. Gateways are not DCM-managed entities; create them with SQL through the Snowflake CLI.
2. For each approved Prod candidate, create a new service from that exact Registry version. Service creation from a Registry version uses the Python `ModelVersion.create_service()` API, so it runs in a Code Bundle entrypoint inside Snowflake rather than on the CI runner (Section 11). Creating a service does not change what callers receive.
3. Smoke-test the candidate service directly, then change routing through the Gateway with `ALTER GATEWAY ... FROM SPECIFICATION`. A `traffic_split` specification requires weights that sum to 100. A `shadow_traffic` specification has one primary endpoint and weighted shadows; shadow traffic is Preview.
4. Verify through the Gateway URL, then record the serving selection. Recovery restores the previous specification. Retire services older than the rollback target after a soak period.

The Gateway owner role needs `BIND SERVICE ENDPOINT` on the account and `USAGE` on the target endpoints. Routing changes typically take effect within a minute ([Gateways](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/gateway); [ALTER GATEWAY](https://docs.snowflake.com/en/sql-reference/sql/alter-gateway)). Pre-Prod validates the same pattern with its own services and Gateway; Prod never routes to a Pre-Prod service.

Rollback must restore the complete compatible path: model version or service, alias or Gateway weights, feature version, signature, dependencies, and monitor configuration.

## 8. Stage 6: Operate inference and monitoring

The companion paper compares Snowflake's inference and monitoring capabilities in detail. For the handover, record the selected inference mode and the operational contract it creates:

| Need | Operational handover |
|---|---|
| Warehouse batch inference | Input query, model version or alias, output table, schedule, warehouse, and owner |
| Asynchronous `run_batch()` | Input and output stages, compute pool, completion check, retry policy, and owner |
| Real-time model service | Request/response schema, endpoint access, capacity, telemetry, availability target, and owner |

See the [inference overview](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/inference-overview) for the capability comparison.

Monitoring needs a prediction record and a ground-truth plan. Define the prediction identifier, outcome table, label finality, expected delay, unmatched outcomes, late arrivals, cohorts, minimum sample sizes, thresholds, and response actions.

A **model version monitor** reads a named, typed source table or view for one Registry version. A **Gateway monitor** compares services behind a Gateway. **Auto Capture** can be enabled on a service without a Gateway, but failed requests capture no request or response data and other limits can create gaps. Direct-service captures must be flattened and typed before a version monitor can use them. Application telemetry and business transaction identifiers therefore remain the operational source of truth ([model observability](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/model-observability); [Auto Capture](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/auto-capture-inference-logs)).

Monitoring should lead to a defined operating action: investigate, retain the incumbent, retrain a candidate, roll back, or retire the model. Each monitor therefore needs an owner and decision rules.

## 9. Stage 7: Decide when to retrain

Periodic retraining is common, but a calendar is only one trigger. Valid policies include:

- A schedule, such as monthly or quarterly.
- A minimum volume of new, trustworthy labelled data.
- A material feature or source change.
- Performance degradation after ground truth becomes available.
- Drift followed by investigation.
- A business event or manual model review.
- A combination of these conditions.

A useful pattern is to schedule **evaluation of retraining need**, not unconditional promotion:

```text
Scheduled or event-driven check
        ↓
Enough new and trustworthy labelled data?
        ↓
Current model requires reconsideration?
        ↓
Run training pipeline
        ↓
Evaluate candidate
        ↓
Approve and promote, or retain incumbent
```

The same **version-controlled Task Graph definition** can be deployed as separate task objects in DEV, Pre-Prod, and PROD. DEV can run it on demand, Pre-Prod can use it for pipeline-release validation, and PROD can attach a schedule or trigger. Object names, configuration, ownership, and grants change by environment; the promoted release identifier and workflow contract should remain traceable.

## 10. How the way of working changes

### Data scientist

- Continues to use Notebooks for exploration and communication.
- Moves reusable logic into modules with tests and explicit contracts.
- Records runs, metrics, configuration, and candidate models through Experiments and the Registry.
- Defines expected model behaviour and acceptance thresholds with domain owners.
- Participates in investigation and model improvement; production support ownership is agreed rather than assumed.

### ML engineer or platform engineer

- Packages Code Bundles, and optionally NPOs or ML Jobs, and maintains runtime environments.
- Builds the Task Graph, CI/CD, environment configuration, and service identity.
- Implements deployment, promotion, rollback, telemetry, and operational controls.
- Ensures that model, feature, and pipeline versions remain compatible.

### Data engineer or data owner

- Owns source and feature data contracts, quality, freshness, retention, and change communication.
- Maintains shared transformations where appropriate.
- Provides authoritative ground truth and its expected availability.

### Production or model owner

- Accepts the release decision and production risk.
- Owns alerts, incidents, rollback, exception handling, review cadence, and retirement.
- Confirms that monitoring thresholds result in defined actions.

The key organisational change is explicit responsibility across development, engineering, data, and production ownership. The production system can then be operated independently of one person's notebook state or privileges.

## 11. Security, CI/CD, and ownership baseline

Project initiation and production delivery have distinct owners:

| Asset | Default owner |
|---|---|
| ML repository template and CI templates | ML platform team |
| Project repository, branch policy, and code ownership | Product or model team |
| Git API integration and authentication policy | Platform and security teams |
| Private Git-backed Workspace | Individual data scientist |
| DEV schema, approved compute, and developer grants | Platform team through delegated project roles |
| Code Bundle and Task Graph releases | ML engineering or CI service role |
| Production model, promotion policy, and incidents | Production or model owner |

| Role | Primary responsibility |
|---|---|
| `ML_DEVELOPER` | Develop and register candidates in DEV using approved data and compute |
| `ML_ENGINEER` | Deploy Code Bundles, Task Graphs, monitors, and supported infrastructure |
| `ML_PROD_OWNER` | Own production models, services, monitors, and incident decisions |
| `ML_SERVICE` | Provide narrow unattended execution or CI identity; no human login |

CI/CD should use workload identity federation rather than a long-lived credential and separately validate code, model quality, Snowflake object changes, and post-deployment behaviour.

### Orchestration: who runs what

A recurring question is whether CI/CD or Snowflake should orchestrate the MLOps lifecycle. The answer is both, separated by **loop** rather than by tool. Under the retrain-in-target strategy, four distinct state changes occur, each with its own owner:

| Loop or decision | Trigger | Orchestrator | Durable record |
|---|---|---|---|
| 1. Pipeline release (code) | Pull-request merge | CI/CD, for example GitHub Actions | Source release, release stage path, Code Bundle, suspended Task Graph, Pre-Prod pipeline result |
| 2. Prod candidate (model) | Schedule, retraining policy, or manual run | Snowflake: Task Graph executing the Code Bundle | Feature and Dataset versions, Experiment run, Registry candidate, screening result |
| 3. Approval | Accountable owner | Snowflake record written by the production owner role | Promotion decision for one exact candidate and its evidence |
| 4. Serving activation | Approval exists | CI/CD executes; Snowflake enforces | Alias or Gateway configuration and serving selection |

The governing rule is that **CI/CD never holds the truth**. Every CI job reads the relevant Snowflake record first and fails closed when evidence is missing or does not match. Loop 2 stays in Snowflake because Prod candidates train on Prod-governed data, can run longer than a CI runner should wait, and can be started by monitoring. CI's responsibility for a pipeline release ends when a verified pipeline is present in Prod; resuming its schedule is the final verification step.

Loop 2 must re-enter CI before activation so that the change remains reviewable. Two return paths are practical:

- **Polling (simplest):** a scheduled workflow queries for candidates that are screened `accepted`, have an approval record, and are not yet serving.
- **Push:** a Snowflake notification integration calls a webhook that starts a `repository_dispatch` workflow. This is faster but requires a CI token stored as a Snowflake secret.

Neither path may promote a model directly from a drift alert or a screening result.

### Tool boundaries: DCM, Snowflake CLI, and Code Bundles

These three are frequently confused because all three appear in a release pipeline. They have different roles:

| Concern | Use | Reason |
|---|---|---|
| Databases, schemas, warehouses, stages, roles, grants, tags, tasks and Task Graphs, alerts, procedures | **DCM Projects** (`snow dcm plan` / `snow dcm deploy`) | Declarative desired state; PLAN output reviewable in the pull request; deployment history per environment project |
| Upload the approved commit to an immutable release path, create the release-specific Code Bundle, write release records, trigger and verify runs | **Snowflake CLI** (`snow stage copy`, `snow sql -x`) | Imperative, release-specific steps that should create a new object per release rather than reconcile one |
| Feature Views, Dataset versions, Experiment runs, model versions | **Created at runtime by the training Code Bundle** (Python: Feature Store, `ExperimentTracking`, `log_model`) | Never created by CI. SQL cannot create a model version from scratch; `CREATE MODEL` and `ADD VERSION` only copy existing models |
| Model service from a Registry version | **Code Bundle deployment entrypoint** (Python `create_service()`), executed with SQL | No documented SQL path, and it keeps `snowflake-ml-python` off the CI runner |
| Alias or default version, tags, Gateway routing, model monitors, serving record | **SQL**: `ALTER MODEL`, `ALTER GATEWAY`, `CREATE MODEL MONITOR`, wrapped in an owner's-rights procedure where the production owner must authorise | Control-plane changes that need no ML library |
| Compute pools and Gateways (create once) | **Snowflake CLI** (`snow sql`, `snow spcs compute-pool`) in the infrastructure workflow | Not DCM-managed entities |
| Training, evaluation, and registration | **Code Bundle** executed by a task or SQL file | An execution unit, not a deployment tool |

The Snowflake CLI has no command groups for models, Datasets, Feature Views, Experiments, monitors, or Gateways. It reaches them only through `snow sql`. The practical consequence is to keep Python ML work inside Snowflake and expose it to CI as SQL, as shown in the example below.

DCM Projects became generally available on 7 August 2026. DCM-defined tasks deploy suspended unless the definition declares a `STARTED` target state, so the production graph can remain suspended until verification. DCM grant management does not cover `CALLER` grants ([DCM deployment](https://docs.snowflake.com/en/user-guide/dcm-projects/dcm-projects-use); [DCM supported entities](https://docs.snowflake.com/en/user-guide/dcm-projects/dcm-projects-supported-entities)).

**Alternative: DCM-managed Code Bundles.** `DEFINE CODE BUNDLE` (Preview) lets a DCM project create and update a bundle from a project asset, adding a new version on each deployment. It is a reasonable choice when the bundle should be versioned alongside the rest of the environment. This guide keeps CLI-created, release-specific bundles as the default because DCM cannot adopt a bundle created outside the project; removing the `DEFINE` drops the bundle and all of its versions; a project that manages a bundle cannot be dropped without `PURGE`; and one bundle name per release gives an unambiguous binding between what Pre-Prod validated and what Prod executes.

### Illustrative GitHub Actions shape

The [Snowflake CLI GitHub Action](https://docs.snowflake.com/en/developer-guide/snowflake-cli/cicd/github-action) installs `snow` and, with `use-oidc: true`, configures workload identity federation so that no Snowflake secret is stored in GitHub. The service user trusts the GitHub issuer and an exact subject claim. When a job declares `environment:`, the subject takes the form `repo:<owner>/<repo>:environment:<name>`. DCM-specific composite actions (`snowflakedb/snowflake-actions/dcm/*`) are Preview. The following is a shape, not a tested workflow:

```yaml
# pipeline-release.yaml: loop 1
on:
  push:
    branches: [main]
permissions: {id-token: write, contents: read}
jobs:
  preprod:
    runs-on: ubuntu-latest
    environment: preprod
    env: {SNOWFLAKE_ACCOUNT: myorg-myaccount}   # account identifier is not a secret
    steps:
      - uses: actions/checkout@v4
      - uses: snowflakedb/snowflake-actions@v3
        with: {use-oidc: true}
      - run: snow dcm plan --target PREPROD -x && snow dcm deploy --target PREPROD -x
      - run: snow stage copy . @ML_PREPROD.CHURN.ML_RELEASES/churn-risk/${{ github.sha }}/ --recursive -x
      - run: snow sql -x -f deployment/create_release_bundle.sql --variable "release='${{ github.sha }}'"
      - run: snow sql -x -f deployment/run_preprod_validation.sql   # fails on reject or failed
  prod:
    needs: preprod
    environment: prod        # required reviewers
    # same steps against the PROD target; Task Graph stays suspended until verified
```

### Example: one CI interface for an online serving release

The goal is that CI switches neither languages nor dependencies. The runner installs only the Snowflake CLI and issues SQL. Python that needs `snowflake-ml-python` runs inside Snowflake. Two Snowflake objects provide this, and the split is forced by the platform: `EXECUTE CODE BUNDLE` runs with caller's rights and cannot be called from an owner's-rights procedure, while the privileged state change should run with owner's rights ([EXECUTE CODE BUNDLE](https://docs.snowflake.com/en/sql-reference/sql/execute-code-bundle)).

| Step | Snowflake object | Runs as | CI call |
|---|---|---|---|
| Create and smoke-test the candidate service | `deploy_service.py` entrypoint in the release Code Bundle (Python) | CI service role (caller's rights) | `EXECUTE CODE BUNDLE ... ENTRYPOINT = 'jobs/deploy_service.py'` |
| Verify approval, move Gateway weights, record selection | `ACTIVATE_SERVING` procedure (SQL), defined by DCM | Production owner role (owner's rights) | `CALL ACTIVATE_SERVING(...)` |
| Restore the previous selection | `RECOVER_SERVING` procedure (SQL) | Production owner role | `CALL RECOVER_SERVING(...)` |

The CI service role therefore needs `USAGE` on the Code Bundle and compute pool, `READ` on the model, and `CREATE SERVICE` in the serving schema to create the service, plus `USAGE` on the two procedures. It never receives the production owner role or ownership of the Gateway.

The GitHub workflow contains only SQL:

```yaml
# serving-release.yaml: loop 4 (online reference branch)
on:
  workflow_dispatch:
    inputs:
      version:     {required: true}                  # exact Registry version, for example CANDIDATE_7
      decision_id: {required: true}                  # PROMOTION_DECISION row authorising it
      mode:        {default: 'SHADOW', required: true}  # 'SHADOW' (mirror only) or 'SPLIT' (live canary/cutover)
      weight:      {default: '10', required: true}      # shadow mirror % (0-100) or live split % (1-100)
permissions: {id-token: write, contents: read}
jobs:
  activate:
    runs-on: ubuntu-latest
    environment: prod                 # required reviewers; OIDC subject repo:<org>/<repo>:environment:prod
    env: {SNOWFLAKE_ACCOUNT: myorg-myaccount}
    steps:
      - uses: snowflakedb/snowflake-actions@v3
        with: {use-oidc: true}        # installs snow only; no snowflake-ml-python
      - name: Create and smoke-test the candidate service
        run: |
          snow sql -x -q "EXECUTE CODE BUNDLE ML_PROD.CHURN.CHURN_TRAINING_R_2026_09_11_1
            ENTRYPOINT = 'jobs/deploy_service.py'
            ARGUMENTS = ('--version', '${{ inputs.version }}')"
      - name: Apply Gateway routing (procedure re-checks approval)
        run: |
          snow sql -x -q "CALL ML_PROD.CONTROL.ACTIVATE_SERVING(
            '${{ inputs.version }}', '${{ inputs.decision_id }}',
            '${{ inputs.mode }}', ${{ inputs.weight }})"
      - name: Recover on failure
        if: failure()
        run: snow sql -x -q "CALL ML_PROD.CONTROL.RECOVER_SERVING()"
```

The deployment entrypoint ships in the same release Code Bundle as training, so it is reviewed and versioned with the pipeline release. Enabling `autocapture=True` at service creation (an immutable service property) logs requests and responses so that a Gateway Model Monitor (`CREATE MODEL MONITOR ... WITH MODEL = ... GATEWAY = ...`) can compare a shadow or canary challenger against the primary incumbent service (`BASE_SERVICE`). The entrypoint is idempotent and writes a durable receipt rather than relying on process output:

```python
# jobs/deploy_service.py (illustrative)
import argparse
from snowflake.snowpark.context import get_active_session
from snowflake.ml.registry import Registry

args = argparse.ArgumentParser()
args.add_argument("--version", required=True)
version = args.parse_args().version

session = get_active_session()
mv = Registry(session, database_name="ML_PROD", schema_name="CHURN") \
    .get_model("CHURN_DETECTOR").version(version)

service = f"ML_PROD.SERVING.CHURN_DETECTOR_{version}"
if not session.sql(f"SHOW SERVICES LIKE 'CHURN_DETECTOR_{version}' IN SCHEMA ML_PROD.SERVING").collect():
    mv.create_service(service_name=service, service_compute_pool="ML_PROD_SERVE_POOL",
                      ingress_enabled=True, autocapture=True)

# Smoke-test the exact candidate before any traffic moves; fail the run if it does not pass.
mv.run(session.table("ML_PROD.CHURN.SMOKE_TEST_INPUT"), function_name="predict",
       service_name=service).collect()
session.sql("INSERT INTO ML_PROD.CONTROL.SERVICE_DEPLOYMENT (MODEL_VERSION, SERVICE_NAME, STATUS) "
            "SELECT ?, ?, 'SMOKE_TESTED'", params=[version, service]).collect()
```

The activation procedure is plain SQL, so it needs no Python dependency. DCM can define it with `DEFINE PROCEDURE`, owned by the production owner role. It supports both Gateway rollout modes: **`SHADOW`** (`type: shadow_traffic`, Preview, where the incumbent primary serves 100% of caller responses while mirroring `P_CANDIDATE_WEIGHT`% of requests to the candidate) and **`SPLIT`** (`type: traffic_split`, GA, where weights sum to 100 for canary or 100% cutover). Inputs are checked against the approval and deployment records before any dynamic statement runs:

```sql
CREATE OR REPLACE PROCEDURE ML_PROD.CONTROL.ACTIVATE_SERVING(
    P_VERSION VARCHAR, P_DECISION_ID VARCHAR, P_MODE VARCHAR, P_CANDIDATE_WEIGHT NUMBER)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  incumbent VARCHAR;
  spec VARCHAR;
BEGIN
  IF (NOT REGEXP_LIKE(:P_VERSION, '^[A-Z0-9_]+$')) THEN
    RETURN 'rejected: invalid version identifier';
  END IF;
  IF (:P_MODE NOT IN ('SHADOW', 'SPLIT')) THEN
    RETURN 'rejected: mode must be SHADOW or SPLIT';
  END IF;
  IF (:P_CANDIDATE_WEIGHT < 1 OR :P_CANDIDATE_WEIGHT > 100) THEN
    RETURN 'rejected: weight must be 1-100';
  END IF;
  -- The approval must name this exact version.
  IF (NOT EXISTS (SELECT 1 FROM ML_PROD.CONTROL.PROMOTION_DECISION
                  WHERE DECISION_ID = :P_DECISION_ID
                    AND CANDIDATE_VERSION = :P_VERSION
                    AND DECISION = 'approve')) THEN
    RETURN 'rejected: no matching approval';
  END IF;
  -- The candidate service must have passed its smoke test.
  IF (NOT EXISTS (SELECT 1 FROM ML_PROD.CONTROL.SERVICE_DEPLOYMENT
                  WHERE MODEL_VERSION = :P_VERSION AND STATUS = 'SMOKE_TESTED')) THEN
    RETURN 'rejected: candidate service not smoke-tested';
  END IF;

  SELECT MODEL_VERSION INTO :incumbent FROM ML_PROD.CONTROL.SERVING_SELECTION
    WHERE ENVIRONMENT = 'PROD' AND ACTIVE QUALIFY ROW_NUMBER() OVER (ORDER BY SELECTED_AT DESC) = 1;

  IF (:P_MODE = 'SHADOW') THEN
    -- Primary (incumbent) serves 100% of caller responses; candidate receives mirrored shadow requests.
    spec := 'spec:\n  type: shadow_traffic\n  primary:\n'
         || '  - type: endpoint\n    value: ML_PROD.SERVING.CHURN_DETECTOR_' || :incumbent || '!inference\n'
         || '  shadow:\n'
         || '  - type: endpoint\n    value: ML_PROD.SERVING.CHURN_DETECTOR_' || :P_VERSION || '!inference\n'
         || '    weight: ' || :P_CANDIDATE_WEIGHT || '\n';
  ELSE
    -- Live traffic split across incumbent and candidate (weights sum to 100).
    spec := 'spec:\n  type: traffic_split\n  split_type: custom\n  targets:\n'
         || '  - type: endpoint\n    value: ML_PROD.SERVING.CHURN_DETECTOR_' || :incumbent || '!inference\n'
         || '    weight: ' || (100 - :P_CANDIDATE_WEIGHT) || '\n'
         || '  - type: endpoint\n    value: ML_PROD.SERVING.CHURN_DETECTOR_' || :P_VERSION || '!inference\n'
         || '    weight: ' || :P_CANDIDATE_WEIGHT || '\n';
  END IF;
  EXECUTE IMMEDIATE 'ALTER GATEWAY ML_PROD.SERVING.CHURN_GATEWAY FROM SPECIFICATION $$' || :spec || '$$';

  -- Record the change; only a 100% live SPLIT marks the candidate as the active primary.
  INSERT INTO ML_PROD.CONTROL.SERVING_SELECTION
    (SELECTION_ID, ENVIRONMENT, MODEL_NAME, MODEL_VERSION, DECISION_ID,
     VERIFICATION_STATUS, SELECTED_BY, SELECTED_AT, ACTIVE)
  SELECT UUID_STRING(), 'PROD', 'CHURN_DETECTOR', :P_VERSION, :P_DECISION_ID,
         :P_MODE || '_' || :P_CANDIDATE_WEIGHT, CURRENT_USER(), CURRENT_TIMESTAMP(),
         (:P_MODE = 'SPLIT' AND :P_CANDIDATE_WEIGHT = 100);
  RETURN 'activated ' || :P_VERSION || ' in ' || :P_MODE || ' mode at ' || :P_CANDIDATE_WEIGHT || '%';
END;
$$;
```

The batch-only default uses the same procedure shape without the Gateway statement. The privileged change is `ALTER MODEL ML_PROD.CHURN.CHURN_DETECTOR VERSION <version> SET ALIAS = PRODUCTION`, after `UNSET ALIAS` on the previous version, because an alias can be held by only one version. That path needs no Code Bundle step at all.

These snippets show the contract and have not been executed. Before adoption, validate that `create_service()` and `ModelVersion.run(service_name=...)` behave as expected inside a Code Bundle on the chosen runtime, and that `EXECUTE CODE BUNDLE` returns only after the entrypoint completes so that CI can rely on its exit status. If the call returns early, add a polling step on the deployment receipt.

### Separation of duties for activation

The CI identity naturally maps to the engineer or service role, while serving selection should be written only by the production owner. Do not grant the production owner role to the CI user. Instead, deploy an owner's-rights procedure (DCM can define it) owned by the production owner role. The procedure verifies that an approval exists for the exact model version and evidence before it changes the alias or Gateway and records the serving selection. The CI identity receives `USAGE` on that procedure only. A GitHub Environment reviewer is an additional control, not a substitute for the Snowflake approval record.

ML Jobs generally require compute-pool, schema `CREATE SERVICE`, and payload-stage access. Real-time services require model `READ` or ownership, compute-pool access, schema `CREATE SERVICE`, and endpoint privileges when ingress is enabled; stage access is not a general service prerequisite. Warehouse model calls require model `USAGE` ([ML Jobs access](https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-jobs/access-control-requirements); [real-time privileges](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/real-time-inference-rest-api#label-real-time-inference-required-privileges)).

## 12. Practical implementation sequence

1. Select one representative model developed in a Git-backed Workspace.
2. Extract a parameterised training entry point and run it on demand in DEV.
3. Pin the project, runtime, Registry dependencies, and target platforms.
4. Record Experiment, model, configuration, metrics, and lineage outputs.
5. Split the workflow into Task Graph steps and test retries and idempotency.
6. Deploy to Pre-Prod with production-like data contracts and a narrow execution identity. Then run the same approved source in Prod to create a new candidate.
7. Implement quality gates and a separate promotion decision.
8. Deploy the selected inference path and ground-truth collection in PROD.
9. Configure monitoring, alerts, rollback, support, and retirement.
10. Add an appropriate scheduled or event-driven retraining policy.

This sequence creates a training and model-promotion system that can be run, tested, approved, operated, and improved independently of the original experiment.

## 13. References

- Create and deploy ML pipelines — https://docs.snowflake.com/en/developer-guide/snowflake-ml/create-pipelines-deploy
- Code Bundles — https://docs.snowflake.com/en/developer-guide/code-bundles/code-bundles
- EXECUTE CODE BUNDLE — https://docs.snowflake.com/en/sql-reference/sql/execute-code-bundle
- Notebooks in Workspaces — https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-schedule
- Custom Runtime Images — https://docs.snowflake.com/en/developer-guide/snowflake-ml/custom-runtime-images
- Experiments — https://docs.snowflake.com/en/developer-guide/snowflake-ml/experiments
- ML Jobs — https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-jobs/overview
- Task Graphs — https://docs.snowflake.com/en/developer-guide/snowflake-python-api/snowflake-python-managing-tasks
- Model Registry — https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview
- Inference overview — https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/inference-overview
- ML Observability — https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/model-observability
- Auto Capture — https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/auto-capture-inference-logs
- Gateways — https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/stable-endpoints-api-reference
- DCM supported objects — https://docs.snowflake.com/en/user-guide/dcm-projects/dcm-projects-supported-entities
- Deploy and manage DCM Projects — https://docs.snowflake.com/en/user-guide/dcm-projects/dcm-projects-use
- Snowflake CLI GitHub Action — https://docs.snowflake.com/en/developer-guide/snowflake-cli/cicd/github-action
- Gateways (SPCS) — https://docs.snowflake.com/en/developer-guide/snowpark-container-services/gateway
- ALTER GATEWAY — https://docs.snowflake.com/en/sql-reference/sql/alter-gateway

Product capabilities and availability status referenced as of September 2026.