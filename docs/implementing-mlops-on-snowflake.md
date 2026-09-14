# From Notebook to Production with Snowflake ML

*A practical path from experimentation to repeatable training, controlled promotion, and retraining*

## 1. Starting point and target state

Consider a data scientist developing a churn model in a Notebook in a Git-backed Workspace. The notebook loads data, creates features, trains several candidates, evaluates them, and registers a promising version. The work is valuable, but it is not yet independently operable. Package installation may be interactive, parameters may be embedded in cells, execution may depend on the author's privileges, and the criteria for accepting a new model may exist only in the author's reasoning.

The practical MLOps objective is to turn that experiment into this repeatable flow:

```text
Notebook experiment
        ↓
Repeatable training workflow
        ↓
On-demand execution in DEV
        ↓
Automated validation in TEST/QA
        ↓
Candidate model and evidence
        ↓
Separate promotion decision
        ↓
Inference and monitoring in PROD
        ↓
Scheduled or triggered evaluation and retraining
```

The first production-oriented artefact is a repeatable training workflow that is testable and executable by someone other than its author. Once validated, the workflow can be operated on demand, on a schedule, or in response to an event.

This paper assumes Notebooks in Workspaces and complements *MLOps with Snowflake ML*, which describes the broader lifecycle and platform capabilities.

## 2. Initiate the project

The project should begin with a repository and an agreed operating boundary, rather than an empty notebook. The repository is the source of truth; a Workspace is a development environment; an NPO or ML Job is an execution unit; and the Registry model version is the trained artefact.

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

Production deployment should not depend on a developer's private Workspace. After pull-request approval, CI/CD copies the approved repository contents to an internal or temporary stage, creates or versions an NPO from that stage, or submits the packaged Python project as an ML Job. This preserves the commit-to-release relationship ([production NPO workflow](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-workflow-scenarios)).

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
Environment-specific NPO or ML Job and Task Graph
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
7. After approval, CI/CD identifies the merge commit as a release candidate and deploys it to TEST/QA. The production deployment later uses that same release identifier.

OAuth is a practical choice for interactive Workspace users. Automated pipelines normally use a non-interactive Git and Snowflake authentication method approved by the organisation, with workload identity federation preferred for Snowflake CI authentication.

The CI workflow can implement the release path as these ordered stages:

```yaml
validate:
  - run: unit and configuration tests
  - run: DEV data-contract and training smoke tests
package:
  - record: commit SHA, dependency lock, and release identifier
  - upload: repository snapshot to the TEST release stage
deploy_test:
  - create: release-specific NPO or ML Job definition
  - run: TEST/QA training and inference validation
promote_release:
  - require: TEST/QA approval
  - upload: the same repository snapshot to the PROD release stage
  - deploy: PROD NPO or ML Job and Task Graph in suspended state
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
- Machine-readable success, rejection, or failure status.

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

There are two practical execution units.

### Versioned Notebook Project Object

An approved Workspace snapshot can be deployed as a versioned **Notebook Project Object** (NPO). This preserves the notebook as the executable entry point while separating deployed content from ongoing edits. It suits workflows that remain understandable and maintainable as a notebook project and do not require extensive reuse outside it ([NPO scheduling](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-schedule)).

Standardise the NPO version, main file, dependency file, runtime or CRE, query warehouse, compute pool, and environment arguments. Direct `EXECUTE NOTEBOOK PROJECT` uses caller-as-user semantics, so development execution can still reflect a person's privileges; this must change before production.

An on-demand DEV validation can execute the deployed project explicitly:

```sql
EXECUTE NOTEBOOK PROJECT ML_DEV.CHURN.CHURN_TRAINING
  MAIN_FILE = 'notebooks/train.ipynb'
  COMPUTE_POOL = 'ML_DEV_CPU_POOL'
  RUNTIME = 'cre@ml_cpu_py311_v3'
  QUERY_WAREHOUSE = 'ML_DEV_WH'
  ARGUMENTS = '--environment dev --config config/dev.yaml'
  REQUIREMENTS_FILE = 'requirements.txt';
```

### ML Job

Use an **ML Job** when training is modular Python, needs project packaging, requires larger or multi-node compute, or should run independently of a notebook service. Use `@remote` for a function, file or directory submission for a project, and `MLJobDefinition` for a reusable payload executed with different parameters ([ML Jobs](https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-jobs/overview)).

NPOs and ML Jobs are alternative execution units for the same training contract. A team can begin with an NPO and later move the entry point to an ML Job while retaining its data, evaluation, registration, and promotion contracts.

For an NPO-based release, CI/CD uploads the approved commit to an immutable stage path. A release-specific NPO name provides an unambiguous binding between the code validated in TEST/QA and the deployed object:

```sql
CREATE NOTEBOOK PROJECT ML_TEST.CHURN.CHURN_TRAINING_R_2026_09_11_1
  FROM '@ML_TEST.CHURN.ML_RELEASES/churn-risk/2026.09.11.1'
  COMMENT = 'churn-risk release 2026.09.11.1';
```

The release pipeline records the commit SHA, release identifier, stage path, and NPO name together. File upload is performed by CI before this SQL runs. An organisation that manages multiple versions within one NPO can instead use `ALTER NOTEBOOK PROJECT ... ADD VERSION`, but its deployment process must record and verify the effective version used by each task.

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

During development and TEST/QA, the Task Graph can run on demand. Production scheduling or event triggers are introduced after the graph is validated and the retraining policy is approved.

For a single-NPO starting point, the scheduling fragment is explicit about the release-specific NPO and runtime configuration. It assumes the NPO, warehouse, compute pool, task-owner grants, monitoring, and failure notification have already passed TEST/QA. CI substitutes the approved release identifier before executing the deployment SQL:

```sql
CREATE OR REPLACE TASK ML_PROD.CHURN.CHURN_TRAINING_TASK
  WAREHOUSE = ML_PROD_WH
  SCHEDULE = 'USING CRON 0 4 * * SUN Europe/Stockholm'
AS
  EXECUTE NOTEBOOK PROJECT ML_PROD.CHURN.CHURN_TRAINING_R_2026_09_11_1
    MAIN_FILE = 'notebooks/train.ipynb'
    COMPUTE_POOL = 'ML_PROD_CPU_POOL'
    RUNTIME = 'cre@ml_cpu_py311_v3'
    QUERY_WAREHOUSE = 'ML_PROD_WH'
    ARGUMENTS = '--environment prod --config config/prod.yaml'
    REQUIREMENTS_FILE = 'requirements.txt';

-- Resume only after deployment checks confirm the release and grants.
ALTER TASK ML_PROD.CHURN.CHURN_TRAINING_TASK RESUME;
```

For a multi-step graph, the release process deploys the graph definition instead. The task-owner role receives the minimum privileges needed by every step and is tested in TEST/QA before the PROD graph is resumed.

## 6. Stage 4: Validate the pipeline release in TEST/QA

The pipeline release moves through environments with an immutable release identifier. Model promotion remains a separate decision in Stage 5.

| Environment | Purpose | Expected outcome |
|---|---|---|
| DEV | Fast iteration and on-demand execution | Reproducible workflow and candidate evidence |
| TEST/QA | Production-like data contracts, dependencies, privileges, and failure testing | Release decision for pipeline and model |
| PROD | Governed execution, controlled promotion, inference, and monitoring | Operated model with accountable owner |

Separate databases are a useful starting point; separate accounts can provide stronger isolation where governance, resilience, or data locality requires it.

Two independent things move through these environments:

**Pipeline release.** Promote one version-controlled commit or release containing the Python package, NPO or ML Job entry point, Task Graph definition, tests, dependency policy, and deployment definitions. Deploy that same release separately into DEV, TEST/QA, and PROD with environment-specific object names, configuration, ownership, and grants. TEST/QA approves the pipeline release; PROD deployment does not rebuild it from an untracked Workspace state.

**Candidate model.** A pipeline run produces a model candidate and its evidence. Candidate promotion follows the quality and approval process in Stage 5 and remains separate from deployment of the training pipeline. A new pipeline release does not automatically replace the production model, and a newly approved model does not necessarily require a new pipeline release.

### What TEST/QA should prove

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

The same **version-controlled Task Graph definition** can be deployed as separate task objects in DEV, TEST/QA, and PROD. DEV can run it on demand, TEST/QA can use it for release validation, and PROD can attach a schedule or trigger. Object names, configuration, ownership, and grants change by environment; the promoted release identifier and workflow contract should remain traceable.

## 10. How the way of working changes

### Data scientist

- Continues to use Notebooks for exploration and communication.
- Moves reusable logic into modules with tests and explicit contracts.
- Records runs, metrics, configuration, and candidate models through Experiments and the Registry.
- Defines expected model behaviour and acceptance thresholds with domain owners.
- Participates in investigation and model improvement; production support ownership is agreed rather than assumed.

### ML engineer or platform engineer

- Packages NPOs or ML Jobs and maintains runtime environments.
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
| NPO or ML Job and Task Graph releases | ML engineering or CI service role |
| Production model, promotion policy, and incidents | Production or model owner |

| Role | Primary responsibility |
|---|---|
| `ML_DEVELOPER` | Develop and register candidates in DEV using approved data and compute |
| `ML_ENGINEER` | Deploy NPOs, Jobs, Task Graphs, monitors, and supported infrastructure |
| `ML_PROD_OWNER` | Own production models, services, monitors, and incident decisions |
| `ML_SERVICE` | Provide narrow unattended execution or CI identity; no human login |

CI/CD should use workload identity federation rather than a long-lived credential and separately validate code, model quality, Snowflake object changes, and post-deployment behaviour.

**DCM Projects** can manage supported scaffolding such as databases, schemas, warehouses, stages, tasks, roles, grants, tags, and project-owned dynamic tables. They do not currently manage `MODEL`, `DATASET`, `FEATURE VIEW`, `EXPERIMENT`, or `MODEL MONITOR` objects ([DCM support](https://docs.snowflake.com/en/user-guide/dcm-projects/dcm-projects-supported-entities)). Models and ML objects therefore need explicit deployment steps in the pipeline.

ML Jobs generally require compute-pool, schema `CREATE SERVICE`, and payload-stage access. Real-time services require model `READ` or ownership, compute-pool access, schema `CREATE SERVICE`, and endpoint privileges when ingress is enabled; stage access is not a general service prerequisite. Warehouse model calls require model `USAGE` ([ML Jobs access](https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-jobs/access-control-requirements); [real-time privileges](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/real-time-inference-rest-api#label-real-time-inference-required-privileges)).

## 12. Practical implementation sequence

1. Select one representative model developed in a Git-backed Workspace.
2. Extract a parameterised training entry point and run it on demand in DEV.
3. Pin the project, runtime, Registry dependencies, and target platforms.
4. Record Experiment, model, configuration, metrics, and lineage outputs.
5. Split the workflow into Task Graph steps and test retries and idempotency.
6. Deploy to TEST/QA with production-like data contracts and a narrow execution identity.
7. Implement quality gates and a separate promotion decision.
8. Deploy the selected inference path and ground-truth collection in PROD.
9. Configure monitoring, alerts, rollback, support, and retirement.
10. Add an appropriate scheduled or event-driven retraining policy.

This sequence creates a training and model-promotion system that can be run, tested, approved, operated, and improved independently of the original experiment.

## 13. References

- Create and deploy ML pipelines — https://docs.snowflake.com/en/developer-guide/snowflake-ml/create-pipelines-deploy
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

Product capabilities and availability status referenced as of September 2026.