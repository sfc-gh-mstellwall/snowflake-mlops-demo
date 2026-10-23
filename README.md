# Snowflake MLOps Demo

A phased demonstration of taking a retail credit-risk early-warning model from exploratory notebooks to a repeatable Code Bundle, a separately approved Prod candidate, warehouse batch serving, and reviewed monitoring.

The synthetic use case estimates whether an existing credit account will enter a defined default state within 90 days. It is for portfolio monitoring and case prioritisation, not automated credit approval or adverse action.

## Operating model

The workshop default is:

```text
Private Git-backed Workspace
  -> exploratory notebooks
  -> tested Python modules
  -> immutable source release
  -> compute-pool Code Bundle
  -> Pre-Prod pipeline validation
  -> same approved source in Prod
  -> new Prod-trained candidate
  -> exact-candidate screening
  -> separate approval
  -> warehouse batch serving
  -> monitoring and reviewed action
```

Two releases stay independent. A pipeline release moves approved source, dependencies and tests. A model release authorises a specific Registry version to serve. Screening `accepted` means the candidate is eligible for that later decision; it is not approval and does not change live serving.

The disposable demo keeps `RAW`, `DEV`, `TEST`, `PROD` and `CONTROL` in one database. `TEST` is the teaching name for **Pre-Prod**. Separate databases in one account remain the production recommendation. ML Jobs and exact-artefact copy remain supported alternatives, not the workshop default.

Do not run this disposable workload in Snowhouse.

### Orchestration and tool boundaries

In production, CI/CD (for example GitHub Actions) orchestrates the **pipeline release** and carries out approved serving changes. Snowflake Tasks orchestrate **Prod training**, and Snowflake holds the approval and serving records that CI must check first. The demo maps onto the production tools as follows:

| Concern | Production tool | In this demo |
|---|---|---|
| Schemas, roles, grants, warehouse, stages, tasks, procedures | DCM Projects | Rendered SQL templates in `deployment/` |
| Upload approved source, create release-specific bundle, record release | Snowflake CLI in CI (`snow stage copy`, `snow sql -x`) | `scripts/build_release.py` + `deployment/05_code_bundle.sql` & `06_environment_releases.sql` |
| Training, evaluation, registration | Code Bundle executed from SQL or a Task Graph | `jobs/train.py` + `src/credit_default/training.py` (showcased in Notebook 04) |
| Feature Views, Datasets, Experiment runs, model versions | Created at runtime by the training Code Bundle (Python) | Notebooks 02–03 (`DEV`) and `src/credit_default/features.py` + `training.py` (`TEST` & `PROD`) |
| Online model service (`autocapture=True`) | Code Bundle deployment entrypoint (`jobs/deploy_service.py`), called from CI by SQL | `jobs/deploy_service.py` + `CONTROL.SERVICE_DEPLOYMENT` |
| Alias, Gateway (`SHADOW` / `SPLIT`), serving record, rollback | Owner's-rights SQL procedures (`ACTIVATE_SERVING`, `RECOVER_SERVING`) called by CI with `snow sql` | `deployment/04_control_contracts.sql` + `src/credit_default/approval.py` (showcased in Notebook 04) |

No GitHub workflow is part of this repository or the demo. See section 11 of `docs/implementing-mlops-on-snowflake.md`.

## End-to-end 4-notebook showcase

The repository showcases the seven-stage MLOps loop across four Snowflake Workspace notebooks:

| Notebook | MLOps Stages | What It Demonstrates |
|---|---|---|
| `notebooks/01_credit_default_exploration.ipynb` | **1. Explore** | Source contract checks (`%%sql`), Snowpark DataFrame API key/grain/null verification, 365-day lookback coverage, and 90-day delayed label finality (`FINALISED` vs. `PENDING`). |
| `notebooks/02_credit_default_feature_engineering.ipynb` | **2. Prepare (Feature Store)** | Feature Store (`Entity("CREDIT_ACCOUNT")`, 3 tiled `FeatureView`s + 3 Snowpark-derived `FeatureView`s registered as `V01` in `DEV_FEATURE_STORE`), raw-vs-derived sample spot checks, and point-in-time retrieval verification (`fs.retrieve_feature_values()`). |
| `notebooks/03_credit_default_model_experiment.ipynb` | **2. Prepare (Datasets) → 3. Train & Screen (DEV)** | Feature Store discovery (`fs.list_entities()`, `fs.list_feature_views()`), feature selection, 90-day finality embargo spines, immutable `fs.generate_dataset()` (`CREDIT_DEVELOPMENT`, `CREDIT_VALIDATION`) with upstream lineage, `ExperimentTracking` runs (one `HistGradientBoostingClassifier` baseline and sequential `Tuner` HPO trials), best-run selection, frozen held-out gates, refit on `CREDIT_REFIT`, evaluation on `CREDIT_HELD_OUT`, and `Model Registry` logging. |
| `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` | **4. Review & Approve → 5. Serve → 6. Monitor → 7. Improve** | Release recording (`SOURCE_RELEASE`, `ENVIRONMENT_DEPLOYMENT`), unattended candidate creation in `Pre-Prod` (`TEST`) and `PROD` (`PIPELINE_ATTEMPT`), fail-closed owner approval (`PROMOTION_DECISION`), `ACTIVATE_SERVING` for **Warehouse Batch** (`SET ALIAS = PRODUCTION`) and **Online Gateway** (`SHADOW` vs. `SPLIT`), delayed 90-day outcome replay (`V_PREDICTION_OUTCOME_MATURITY`), and full-path rollback (`RECOVER_SERVING`). |

## Repository structure

```text
config/            Environment bindings (DEV, Pre-Prod/TEST, PROD) and frozen workflow contract
src/               Shared Snowpark and Snowflake ML package (features, training, evaluation, release, approval, monitoring)
jobs/              Code Bundle entrypoints: jobs/train.py (training) and jobs/deploy_service.py (SPCS service + smoke test)
deployment/        Snowflake bootstrap, verification, inventory, control procedures, Code Bundles, monitoring, and teardown SQL
docs/              Architecture papers and presentation/demo runbook
notebooks/         Four Snowflake Workspace notebooks (01 Explore -> 02 Features -> 03 Experiment -> 04 Release, Serving & Monitoring)
scripts/           SQL template renderer (render_sql.py) and Code Bundle payload builder (build_release.py)
project.yaml       Platform object names, compute, and synthetic-data settings
00_workspace_setup.sql Numbered compute prerequisite for a fresh target account
```

## Phase 1

Phase 1 creates an isolated Snowflake environment containing:

- A disposable database with `RAW`, `DEV`, `TEST` (Pre-Prod), `PROD`, and `CONTROL` schemas.
- Dedicated demo roles, warehouse, CPU compute pool, and internal stages.
- Documented customer and revolving-credit account dimensions.
- Dated financial estimates, daily servicing snapshots, payments, contacts, account events, and first-default events.
- Monthly account observations with finalised and pending 90-day outcomes.
- Stable and controlled-drift periods.
- Training and scoring views plus durable pipeline-control tables.

No external data, network access, or credentials are required to generate the dataset.

## Prerequisites

This demonstration runs from a private Git-backed Workspace in the target Snowflake account. A local clone and local Python environment are not required.

Before starting, confirm that the target account provides:

- A Git API integration and authentication method that can read `https://github.com/sfc-gh-mstellwall/snowflake-mlops-demo`.
- A role that can create roles, databases, warehouses, compute pools, schemas, stages, tasks, experiments, models, notebook projects, and model monitors, and grant the required account privileges. The supplied administrative SQL uses `ACCOUNTADMIN`.
- An x86 compute pool for a Workspace notebook service. The repository default is `CRISK_DEMO_POOL` with instance family `GEN_X64_G2_8`.
- Snowflake Container Runtime CPU 2.9. The repository assumes its bundled packages, including PyYAML, rather than reinstalling them. See the [CPU 2.9 package list](https://docs.snowflake.com/en/developer-guide/snowflake-ml/container-runtime/releases/cpu/2_9).

If `CRISK_DEMO_POOL` is missing, run `00_workspace_setup.sql` in a Workspace SQL editor with the administrative role before creating the notebook service. The script creates only the initial compute pool. The rendered bootstrap later adopts the same pool idempotently, and teardown removes it.

If you change the compute-pool name or settings in `project.yaml`, make the same changes in `00_workspace_setup.sql` before running either script.

## Open the Git-backed Workspace

1. Sign in to the intended demonstration account. Do not use an account where the configured demo object names belong to another workload.
2. In Snowsight, open **Projects → Workspaces → From Git repository**.
3. Select the approved Git API integration and authentication method, then use `https://github.com/sfc-gh-mstellwall/snowflake-mlops-demo` and branch `main`.
4. Create the private Git-backed Workspace. Snowflake does not support creating this Workspace with SQL or CLI and attaching Git later.
5. Review `project.yaml`. Keep `project.prefix` ending in `_DEMO`; every destructive account object must begin with that exact prefix.
6. If the prerequisite compute pool is missing, open and run `00_workspace_setup.sql`.
7. Open `scripts/render_sql.py` and connect it to a notebook service using `CRISK_DEMO_POOL` and Snowflake Container Runtime CPU 2.9.

Each user creates a separate private Git-backed Workspace. Collaboration and updates use repository branches, commits, pull requests, and the Workspace Git controls rather than Workspace sharing.

## Render and run Phase 1

With `scripts/render_sql.py` open and connected to the notebook service, select **Run** in the Python file editor. The script detects the Workspace notebook kernel, reads `project.yaml`, and creates `build/` at the repository root. Python files in Workspaces run as complete files and show output in the **Output** tab.

PyYAML is already included in Container Runtime CPU 2.9, so no package installation is required to render the SQL.

Review the generated files in `build/` before executing them:

```text
build/01_bootstrap.sql
build/02_inventory.sql
build/03_verify_data.sql
build/04_control_contracts.sql
build/05_code_bundle.sql
build/06_environment_releases.sql
build/07_monitoring.sql
build/99_teardown.sql
```

Open `build/01_bootstrap.sql` in the Workspace SQL editor and run it with a role that can create roles, databases, warehouses, compute pools, and account-level task grants. The default script selects `ACCOUNTADMIN`; change that only if the target account uses a different administrative role with the required privileges. Its final result sets summarise row and account counts, temporal coverage, label availability, default prevalence, controlled drift, and product mix.

Next, open and run `build/02_inventory.sql`. It verifies that the configured account-level resources and current lifecycle objects are present. Its `SHOW` result sets are an object inventory rather than a pass/fail gate; empty results identify objects that are not present in that category.

Then open and run `build/03_verify_data.sql`. It verifies the generated data rather than the object inventory: row counts, temporal coverage, labels, controlled drift, operational segments, training-label finality, and key uniqueness. Continue to notebook development only when `PHASE_1_STATUS` is `PASS` and the visible population checks are reasonable.

The generated `build/` directory is intentionally ignored by Git. Commit changes to configuration, templates, scripts, tests, and notebooks, not account-specific rendered SQL.

## Run Phase 2

After Phase 1 passes, open `notebooks/01_credit_default_exploration.ipynb` in the same Git-backed Workspace and connect it to the Container Runtime CPU 2.9 notebook service.

Run the notebook from top to bottom. It uses the Snowpark DataFrame API (defining each source table once and pushing down aggregations to Snowflake), with a native Workspace SQL cell for metadata inspection, to:

- Inspect customer and facility dimensions before any label relation.
- Establish the grain, keys, relationships, and date coverage of each source fact.
- Examine balance, utilisation ingredients, delinquency, payments, contacts, and account events through time.
- Introduce default events and delayed label availability separately from predictors.
- Record provisional profile, balance, payment, and delinquency feature hypotheses.

The notebook is Snowflake Workspace-only. It has no local connection fallback and must not be run before the Phase 1 objects exist. Phase 2 does not train or register a model.

## Run Phase 3

First open `notebooks/02_credit_default_feature_engineering.ipynb` in the same private Git-backed Workspace and use Container Runtime CPU 2.9. Do not install packages and do not run this demonstration in Snowhouse.

Run the notebook section by section rather than using **Run all**. It is structured as an interactive investigation:

- Retrieve or create the `CREDIT_ACCOUNT` entity only after notebook 01 has established the source grain, explaining how the shared entity key connects features across monthly, daily, and event-level tables.
- Develop profile, balance, payment, contact, delinquency, and native 365-day tiled aggregation features from lower-level dimensions, daily snapshots, and events, defining each source table once where first needed and inspecting `.limit(10)` samples at each step.
- Review window boundaries, `div0null` ratios, missing-value meaning, and selected sample accounts before registering Feature Views (`V01`) in `DEV_FEATURE_STORE`.
- Verify point-in-time feature retrieval (`fs.retrieve_feature_values()`) across all six registered `V01` Feature Views before handing off to notebook 03.

Then open `notebooks/03_credit_default_model_experiment.ipynb`. This notebook starts by discovering the registered Feature Views in `DEV_FEATURE_STORE`, selecting which features to include in the model, and generating the immutable training and validation Datasets. Run it section by section to:

- Discover registered Entities and Feature Views (`fs.list_entities()`, `fs.list_feature_views()`) and inspect their documented feature catalog in `DEV_FEATURE_STORE`.
- Select the six `V01` Feature Views and 41 predictor columns (`numeric_features` and `categorical_features`).
- Inspect `RAW.AVAILABLE_GROUND_TRUTH` finality timing, construct embargoed development and temporal-validation spines (`OUTCOME_FINALITY_DATE < cutoff`), and generate immutable point-in-time `CREDIT_DEVELOPMENT` and `CREDIT_VALIDATION` Datasets via `fs.generate_dataset()` with upstream Feature View lineage.
- Train one `HistGradientBoostingClassifier` baseline in a tracked Experiment run and log it to the Model Registry.
- Run four tracked HPO trials with the Snowflake `Tuner` and select the run with the highest validation average precision.
- Freeze the screening gates, materialise `CREDIT_REFIT` and `CREDIT_HELD_OUT`, refit the selected candidate once, evaluate it on the held-out period, record the conclusion, and inspect lineage.

Every model fit is covered by a context-managed Experiment run, and every successful fitted candidate is logged before that run ends. The refit and conclusion runs are separate closed runs. Registry signature inference uses a Dataset-backed Snowpark DataFrame so source lineage can be preserved. The four-trial HPO budget is an interactive demo choice, not a production tuning policy.

`project.yaml` is used only as the platform hand-off for Snowflake object names and generated-data settings such as the simulated as-of date. Feature versions, temporal cutoffs, model and Experiment names, model parameters, HPO budget, and evaluation gates are introduced in the notebooks at the point where the investigation motivates them. Freezing those choices into a release contract is a later increment, not something the interactive notebooks invent automatically.

There is no prepared `RAW.TRAINING_BASE` or `RAW.ACCOUNT_SNAPSHOT`. Notebook 01 explores warehouse sources, notebook 02 engineers and registers reusable Feature Views (`V01`), and notebook 03 discovers those Feature Views, selects features, generates immutable Datasets, and runs tracked model experiments.

If an error occurs after a run starts, investigate it before starting another run; Snowflake Experiments do not permit two active runs in the same session. The `holdout_revealed` kernel flag is only a reminder and does not protect the hold-out across kernel restarts. Manual candidate selection and the holdout assertion remain presenter gates; do not run those notebooks unattended unchanged.

`build/01_bootstrap.sql` creates every schema and grant required before the notebooks run, including the Feature Store schema, Dataset creation, source references, and `VIEW LINEAGE`. The notebooks create only modelling artefacts that emerge from the investigation: the entity, Feature Views, Datasets, Experiments, and model versions.

Phase 3 creates an entity tag and Feature View metadata in `DEV_FEATURE_STORE`, immutable Dataset versions and Experiment runs in `DEV`, and candidate versions in the Model Registry. These remain experimental artefacts. Logging a model is registration, not screening acceptance, approval or serving activation. The notebooks do not set a champion alias, change a serving selector, create a Code Bundle, or deploy inference. Full lineage inspection requires Enterprise Edition or higher.

The notebook has been statically checked in this repository but has not been executed against a target account. Verify Feature Store, HPO, Registry dependency resolution, plots, and lineage in the intended Workspace before treating Phase 3 as demonstrated.

## Run Phase 4

Before running Notebook 04, execute `build/04_control_contracts.sql` and `build/07_monitoring.sql` in the Workspace SQL editor so that the `TEST_FEATURE_STORE` and `PROD_FEATURE_STORE` schemas, the `CONTROL` governance tables (`SOURCE_RELEASE`, `ENVIRONMENT_DEPLOYMENT`, `PIPELINE_ATTEMPT`, `SERVING_SELECTION`, `SERVICE_DEPLOYMENT`, `PREDICTION_RECORD`, `OPERATIONAL_ACTION`), the `V_PREDICTION_OUTCOME_MATURITY` view, and the owner's-rights stored procedures (`CONTROL.ACTIVATE_SERVING` and `CONTROL.RECOVER_SERVING`) exist.

Then open `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` in the same Git-backed Workspace and run it section by section to demonstrate:

1. **Loop 1 & Loop 2 (Code Bundles & Unattended Candidate Creation):** Record the source release (`R_2026_10_01`), validate the frozen pipeline in `Pre-Prod` (`TEST`), and train/register the production candidate in `PROD` (`PROD_FEATURE_STORE`) via `train_and_register_candidate()`.
2. **Loop 3 (Deterministic Screening vs. Accountable Owner Approval):** Prove that `ACTIVATE_SERVING` rejects an unapproved candidate, then switch to `CRISK_DEMO_PROD_OWNER` to record an `'approve'` row in `CONTROL.PROMOTION_DECISION`.
3. **Loop 4 Default (Warehouse Batch Inference):** Call `CONTROL.ACTIVATE_SERVING(..., 'BATCH', 100)` to move the `PRODUCTION` model alias and score `RAW.SCORING_POPULATION` across pre-drift and post-drift months into `CONTROL.PREDICTION_RECORD`.
4. **Loop 4 Online Branch (Stable Gateway — `SHADOW` vs. `SPLIT`):** Register a challenger candidate (`R_2026_10_15`), verify that online Gateway activation requires a `'SMOKE_TESTED'` receipt from `jobs/deploy_service.py`, and compare the `type: shadow_traffic` (Preview) and `type: traffic_split` (GA) Gateway specifications.
5. **Stages 6 & 7 (Delayed 90-Day Outcomes & Full-Path Rollback):** Replay time across the `2026-01-01` drift boundary using `evaluate_delayed_outcomes()` and `CONTROL.V_PREDICTION_OUTCOME_MATURITY` (keeping `PENDING` labels separate from negative outcomes), record a reviewed operational action in `CONTROL.OPERATIONAL_ACTION`, and execute full-path rollback with `CONTROL.RECOVER_SERVING`.

## Teardown

From the same Git-backed Workspace, rerun `build/02_inventory.sql` and review every listed object. Shut down the Workspace notebook service before executing `build/99_teardown.sql`, because the service uses the configured compute pool. Teardown removes the configured database, warehouse, compute pool, and roles.

The private Git-backed Workspace is not managed by these scripts. Delete it separately through Snowsight after the Snowflake objects have been removed and any intended repository changes have been committed and pushed.

## Documentation

- [Workshop demo runbook](docs/demo-runbook.md)
- [MLOps with Snowflake ML](docs/mlops-with-snowflake-ml.md)
- [From Notebook to Production with Snowflake ML](docs/implementing-mlops-on-snowflake.md)
- [Plan index](.snowflake/cortex/plans/README.md)

## Important limitation

The generated credit data and model workflow are technical teaching assets. Protected characteristics and direct proxies are intentionally excluded. A real credit-risk implementation requires independent model-risk management, fairness testing, explainability, validation, approval, and applicable regulatory controls.