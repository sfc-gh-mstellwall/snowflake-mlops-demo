# Snowflake MLOps Demo

A phased, practical demonstration of moving a retail credit-risk model from interactive development in Snowflake Notebooks in Workspaces to repeatable training, controlled promotion, inference, monitoring, and retraining evaluation.

The synthetic use case estimates whether an existing credit account will enter a defined default state within 90 days. It is designed for portfolio monitoring and case prioritisation, not automated credit approval or adverse action.

## Project status

The repository is intentionally built in reviewable phases:

| Phase | Scope | Status |
|---|---|---|
| 1 | Portable bootstrap, synthetic data, validation, inventory, teardown | Implemented, awaiting target-account execution |
| 2 | Evidence-first interactive development notebook | Implemented, awaiting target Workspace execution |
| 3 | Interactive Feature Store and tracked model experimentation | Implemented, awaiting target Workspace execution |
| 4 | Extract the proven notebook workflow into repeatable training | Planned |
| 5 | ML Job and Task Graph orchestration | Planned |
| 6 | TEST/QA promotion gates and rollback | Planned |
| 7 | Warehouse inference, monitoring, and retraining evaluation | Planned |

Later phase directories such as `src/` and `config/` will be added after the preceding phase has been demonstrated and reviewed.

## Repository structure

```text
deployment/        Snowflake bootstrap, verification, inventory, and teardown templates
docs/              Conceptual and practical MLOps papers
notebooks/         Snowflake Workspace notebooks for interactive development
scripts/           Configuration validation and SQL rendering
tests/             Renderer and destructive-name safety tests
project.yaml       Platform object names, compute, and synthetic-data settings
00_workspace_setup.sql Numbered compute prerequisite for a fresh target account
```

## Phase 1

Phase 1 creates an isolated Snowflake environment containing:

- A disposable database with `RAW`, `DEV`, `TEST`, `PROD`, and `CONTROL` schemas.
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

PyYAML is already included in Container Runtime CPU 2.9, so no package installation is required to render the SQL. The repository tests use Python's standard-library `unittest` framework and require no additional packages.

To run the repository safety tests from the Workspace terminal:

```bash
cd scripts
python -m unittest discover -s ../tests -v
```

Running from `scripts/` matches the working directory used by the Workspace Python editor and validates the same repository-path behaviour.

Review the generated files in `build/` before executing them:

```text
build/01_bootstrap.sql
build/02_inventory.sql
build/03_verify_data.sql
build/99_teardown.sql
```

Open `build/01_bootstrap.sql` in the Workspace SQL editor and run it with a role that can create roles, databases, warehouses, compute pools, and account-level task grants. The default script selects `ACCOUNTADMIN`; change that only if the target account uses a different administrative role with the required privileges. Its final result sets summarise row and account counts, temporal coverage, label availability, default prevalence, controlled drift, and product mix.

Next, open and run `build/02_inventory.sql`. It verifies that the configured account-level resources and current lifecycle objects are present. Its `SHOW` result sets are an object inventory rather than a pass/fail gate; empty results identify objects that are not present in that category.

Then open and run `build/03_verify_data.sql`. It verifies the generated data rather than the object inventory: row counts, temporal coverage, labels, controlled drift, operational segments, training-label finality, and key uniqueness. Continue to notebook development only when `PHASE_1_STATUS` is `PASS` and the visible population checks are reasonable.

The generated `build/` directory is intentionally ignored by Git. Commit changes to configuration, templates, scripts, tests, and notebooks, not account-specific rendered SQL.

## Run Phase 2

After Phase 1 passes, open `notebooks/01_credit_default_exploration.ipynb` in the same Git-backed Workspace and connect it to the Container Runtime CPU 2.9 notebook service.

Run the notebook from top to bottom. It uses Snowpark pandas for bounded interactive exploration, with a native Workspace SQL cell for metadata inspection, to:

- Inspect customer and facility dimensions before any label relation.
- Establish the grain, keys, relationships, and date coverage of each source fact.
- Examine balance, utilisation ingredients, delinquency, payments, contacts, and account events through time.
- Introduce default events and delayed label availability separately from predictors.
- Record provisional profile, balance, payment, and delinquency feature hypotheses.

The notebook is Snowflake Workspace-only. It has no local connection fallback and must not be run before the Phase 1 objects exist. Phase 2 does not train or register a model.

## Run Phase 3

First open `notebooks/02_credit_default_feature_engineering.ipynb` in the same private Git-backed Workspace and use Container Runtime CPU 2.9. Do not install packages and do not run this demonstration in Snowhouse.

Run the notebook section by section rather than using **Run all**. It is structured as an interactive investigation:

- Retrieve or create the account entity only after notebook 01 has established the source grain.
- Develop profile, balance, payment, contact, delinquency, and native 365-day tiled aggregation features from lower-level dimensions, daily snapshots, and events.
- Review window boundaries, ratios, missing-value meaning, and selected records before registering Feature Views.
- Inspect finalised-label timing before choosing development and validation boundaries, without exposing held-out target rates.
- Generate immutable point-in-time development and validation Datasets and inspect retrieved timestamps.
- Inspect selected-account raw-versus-derived values, visual feature trajectories, and Feature View-to-Dataset lineage before handing the Dataset version to notebook 03.

Then open `notebooks/03_credit_default_model_experiment.ipynb` and paste the immutable Dataset version printed by notebook 02. This notebook does not reopen source facts or rebuild Feature Views. Run it section by section to:

- Establish an unfitted prevalence reference.
- Fit a logistic candidate, inspect coefficients and calibration, then test a non-linear candidate.
- Compare monthly review capacity, segment support, and bounded permutation importance.
- Run a small HPO experiment only after recording what was learned from the initial models.
- Manually select a candidate and record the rationale before enabling the held-out section.
- Materialise refit and held-out Datasets only after the manual gate, then refit once, inspect held-out evidence, record a conclusion, and log the final experimental model.

Every model fit is covered by an Experiment run, and every successful fitted candidate is logged before that run ends. Registry signature inference uses a Dataset-backed Snowpark DataFrame so source lineage can be preserved. HPO runs four sequential trials per family by default in the notebook; this is an explicit interactive budget, not a production tuning policy.

`project.yaml` is used only as the platform hand-off for Snowflake object names and generated-data settings such as the simulated as-of date. Feature versions, temporal cutoffs, model and Experiment names, model parameters, HPO budget, and evaluation gates are introduced in the notebooks at the point where the investigation motivates them.

There is no prepared `RAW.TRAINING_BASE` or `RAW.ACCOUNT_SNAPSHOT`. Notebook 01 explores warehouse sources, notebook 02 derives reusable Feature Views and immutable Datasets, and notebook 03 reads only those Dataset versions.

The final Experiment run intentionally remains active across several inspection cells. Complete the final model-logging cell to call `end_run()`. If an error occurs after the run starts, investigate it before starting another run; Snowflake Experiments do not permit two active runs in the same session. The `holdout_revealed` kernel flag is only a reminder and does not protect the hold-out across kernel restarts.

`build/01_bootstrap.sql` creates every schema and grant required before the notebooks run, including the Feature Store schema, Dataset creation, source references, and `VIEW LINEAGE`. The notebooks create only modelling artefacts that emerge from the investigation: the entity, Feature Views, Datasets, Experiments, and model versions.

Phase 3 creates an entity tag and Feature View metadata in `DEV_FEATURE_STORE`, immutable Dataset versions and Experiment runs in `DEV`, and candidate versions in the Model Registry. These remain experimental artefacts: the notebook does not set a champion alias, promote a default, create a scheduled job, or deploy inference. Full lineage inspection requires Enterprise Edition or higher.

The notebook has been statically checked in this repository but has not been executed against a target account. Verify Feature Store, HPO, Registry dependency resolution, plots, and lineage in the intended Workspace before treating Phase 3 as demonstrated.

## Teardown

From the same Git-backed Workspace, rerun `build/02_inventory.sql` and review every listed object. Shut down the Workspace notebook service before executing `build/99_teardown.sql`, because the service uses the configured compute pool. Teardown removes the configured database, warehouse, compute pool, and roles.

The private Git-backed Workspace is not managed by these scripts. Delete it separately through Snowsight after the Snowflake objects have been removed and any intended repository changes have been committed and pushed.

## Documentation

- [MLOps with Snowflake ML](docs/mlops-with-snowflake-ml.md)
- [From Notebook to Production with Snowflake ML](docs/implementing-mlops-on-snowflake.md)

## Important limitation

The generated credit data and model workflow are technical teaching assets. Protected characteristics and direct proxies are intentionally excluded. A real credit-risk implementation requires independent model-risk management, fairness testing, explainability, validation, approval, and applicable regulatory controls.