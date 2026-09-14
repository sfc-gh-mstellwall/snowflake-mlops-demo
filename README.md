# Snowflake MLOps Demo

A phased, practical demonstration of moving a retail credit-risk model from interactive development in Snowflake Notebooks in Workspaces to repeatable training, controlled promotion, inference, monitoring, and retraining evaluation.

The synthetic use case estimates whether an existing credit account will enter a defined default state within 90 days. It is designed for portfolio monitoring and case prioritisation, not automated credit approval or adverse action.

## Project status

The repository is intentionally built in reviewable phases:

| Phase | Scope | Status |
|---|---|---|
| 1 | Portable bootstrap, synthetic data, validation, inventory, teardown | Implemented, awaiting target-account execution |
| 2 | Evidence-first interactive development notebook | Implemented, awaiting target Workspace execution |
| 3 | Repeatable training, Experiments, Model Registry, tests | Planned |
| 4 | ML Job and Task Graph orchestration | Planned |
| 5 | TEST/QA promotion gates and rollback | Planned |
| 6 | Warehouse inference and model monitoring | Planned |
| 7 | Retraining evaluation and optional NPO path | Planned |

Later phase directories such as `src/` and `config/` will be added after the preceding phase has been demonstrated and reviewed.

## Repository structure

```text
deployment/        Snowflake bootstrap, verification, inventory, and teardown templates
docs/              Conceptual and practical MLOps papers
notebooks/         Snowflake Workspace notebooks for interactive development
scripts/           Configuration validation and SQL rendering
tests/             Renderer and destructive-name safety tests
project.yaml       Portable names, compute, data, and model settings
workspace_setup.sql One-time compute prerequisite for a fresh target account
```

## Phase 1

Phase 1 creates an isolated Snowflake environment containing:

- A disposable database with `RAW`, `DEV`, `TEST`, `PROD`, and `CONTROL` schemas.
- Dedicated demo roles, warehouse, CPU compute pool, and internal stages.
- Deterministic monthly account snapshots.
- Finalised and pending 90-day default outcomes.
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

If `CRISK_DEMO_POOL` is missing, run `workspace_setup.sql` in a Workspace SQL editor with the administrative role before creating the notebook service. The script creates only the initial compute pool. The rendered bootstrap later adopts the same pool idempotently, and teardown removes it.

If you change the compute-pool name or settings in `project.yaml`, make the same changes in `workspace_setup.sql` before running either script.

## Open the Git-backed Workspace

1. Sign in to the intended demonstration account. Do not use an account where the configured demo object names belong to another workload.
2. In Snowsight, open **Projects → Workspaces → From Git repository**.
3. Select the approved Git API integration and authentication method, then use `https://github.com/sfc-gh-mstellwall/snowflake-mlops-demo` and branch `main`.
4. Create the private Git-backed Workspace. Snowflake does not support creating this Workspace with SQL or CLI and attaching Git later.
5. Review `project.yaml`. Keep `project.prefix` ending in `_DEMO`; every destructive account object must begin with that exact prefix.
6. If the prerequisite compute pool is missing, open and run `workspace_setup.sql`.
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
build/bootstrap.sql
build/verify_data.sql
build/inventory.sql
build/teardown.sql
```

Open `build/bootstrap.sql` in the Workspace SQL editor and run it with a role that can create roles, databases, warehouses, compute pools, and account-level task grants. The default script selects `ACCOUNTADMIN`; change that only if the target account uses a different administrative role with the required privileges. Its final result sets summarise row and account counts, temporal coverage, label availability, default prevalence, controlled drift, and product mix.

Next, open and run `build/inventory.sql`. It verifies that the configured account-level resources and current lifecycle objects are present. Its `SHOW` result sets are an object inventory rather than a pass/fail gate; empty results identify objects that are not present in that category.

Then open and run `build/verify_data.sql`. It verifies the generated data rather than the object inventory: row counts, temporal coverage, labels, controlled drift, operational segments, training-label finality, and key uniqueness. Continue to notebook development only when `PHASE_1_STATUS` is `PASS` and the visible population checks are reasonable.

The generated `build/` directory is intentionally ignored by Git. Commit changes to configuration, templates, scripts, tests, and notebooks, not account-specific rendered SQL.

## Run Phase 2

After Phase 1 passes, open `notebooks/credit_default_exploration.ipynb` in the same Git-backed Workspace and connect it to the Container Runtime CPU 2.9 notebook service.

Run the notebook from top to bottom. It uses native Workspace SQL cells and Snowpark cell references to:

- Confirm the training data contract, grain, finality, uniqueness, and missingness.
- Visualise pre-holdout monthly target behaviour and development-to-validation stability.
- Discover candidate columns before assigning feature roles.
- Compare numeric and categorical candidate behaviour.
- Define temporal development, validation, and held-out windows.
- Record baseline, evaluation, leakage, and provisional feature decisions for Phase 3.

The notebook is Snowflake Workspace-only. It has no local connection fallback and must not be run before the Phase 1 objects exist. Phase 2 does not train or register a model.

## Teardown

From the same Git-backed Workspace, rerun `build/inventory.sql` and review every listed object. Shut down the Workspace notebook service before executing `build/teardown.sql`, because the service uses the configured compute pool. Teardown removes the configured database, warehouse, compute pool, and roles.

The private Git-backed Workspace is not managed by these scripts. Delete it separately through Snowsight after the Snowflake objects have been removed and any intended repository changes have been committed and pushed.

## Documentation

- [MLOps with Snowflake ML](docs/mlops-with-snowflake-ml.md)
- [From Notebook to Production with Snowflake ML](docs/implementing-mlops-on-snowflake.md)

## Important limitation

The generated credit data and model workflow are technical teaching assets. Protected characteristics and direct proxies are intentionally excluded. A real credit-risk implementation requires independent model-risk management, fairness testing, explainability, validation, approval, and applicable regulatory controls.