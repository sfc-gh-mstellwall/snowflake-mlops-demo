# Snowflake MLOps Demo

A phased, practical demonstration of moving a retail credit-risk model from interactive development in Snowflake Notebooks in Workspaces to repeatable training, controlled promotion, inference, monitoring, and retraining evaluation.

The synthetic use case estimates whether an existing credit account will enter a defined default state within 90 days. It is designed for portfolio monitoring and case prioritisation, not automated credit approval or adverse action.

## Project status

The repository is intentionally built in reviewable phases:

| Phase | Scope | Status |
|---|---|---|
| 1 | Portable bootstrap, synthetic data, validation, inventory, teardown | Implemented, awaiting target-account execution |
| 2 | Evidence-first interactive development notebook | Planned |
| 3 | Repeatable training, Experiments, Model Registry, tests | Planned |
| 4 | ML Job and Task Graph orchestration | Planned |
| 5 | TEST/QA promotion gates and rollback | Planned |
| 6 | Warehouse inference and model monitoring | Planned |
| 7 | Retraining evaluation and optional NPO path | Planned |

Later phase directories such as `notebooks/`, `src/`, and `config/` will be added after the preceding phase has been demonstrated and reviewed.

## Repository structure

```text
deployment/        Snowflake bootstrap, verification, inventory, and teardown templates
docs/              Conceptual and practical MLOps papers
scripts/           Configuration validation and SQL rendering
tests/             Renderer and destructive-name safety tests
project.yaml       Portable names, compute, data, and model settings
workspace_setup.sql One-time compute prerequisite for a fresh target account
requirements-dev.txt
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

## Open as a Git-backed Workspace

This demonstration is designed to run from a private Git-backed Workspace in the target Snowflake account. A local clone and local Python environment are not required.

1. Sign in to the intended demonstration account. Do not use an account where the configured demo object names belong to another workload.
2. In Snowsight, open **Projects → Workspaces → From Git repository**.
3. Select the approved Git API integration and authentication method, then use `https://github.com/sfc-gh-mstellwall/snowflake-mlops-demo` and branch `main`.
4. Create the private Git-backed Workspace. Snowflake does not support creating this Workspace with SQL or CLI and attaching Git later.
5. Review `project.yaml`. Keep `project.prefix` ending in `_DEMO`; every destructive account object must begin with that exact prefix.

Each user creates a separate private Git-backed Workspace. Collaboration and updates use repository branches, commits, pull requests, and the Workspace Git controls rather than Workspace sharing.

## Render and run Phase 1

Repository Python files require an x86 notebook service. If the target account does not already provide a suitable compute pool, open and run `workspace_setup.sql` in the Workspace SQL editor first. It creates the default `CRISK_DEMO_POOL`; the full bootstrap adopts it idempotently and teardown removes it. If you change the compute-pool defaults in `project.yaml`, make the same changes in `workspace_setup.sql` before running either file.

Open `scripts/render_sql.py` in the Workspace and connect it to a notebook service on that pool, using a Python and Container Runtime version compatible with the account. Install the repository development requirements in that service environment from the Workspace terminal:

```bash
uv pip install -r requirements-dev.txt
```

Select **Run** in the Python file editor. With no arguments, the script reads `project.yaml` and creates `build/` at the repository root. Python files in Workspaces run as complete files and show output in the **Output** tab.

The equivalent Workspace terminal command is:

```bash
python scripts/render_sql.py
```

Run the repository safety tests from the same terminal:

```bash
python -m pytest
```

Review the generated files in `build/` before executing them:

```text
build/bootstrap.sql
build/verify_data.sql
build/inventory.sql
build/teardown.sql
```

Open `build/bootstrap.sql` in the Workspace SQL editor and run it with a role that can create roles, databases, warehouses, compute pools, and account-level task grants. The default script selects `ACCOUNTADMIN`; change that only if the target account uses a different administrative role with the required privileges.

Next, open and run `build/verify_data.sql`. Continue to notebook development only when `PHASE_1_STATUS` is `PASS` and the visible population checks are reasonable.

The generated `build/` directory is intentionally ignored by Git. Commit changes to configuration, templates, scripts, tests, and notebooks, not account-specific rendered SQL.

## Teardown

From the same Git-backed Workspace, run `build/inventory.sql` and review every listed object. Shut down the Workspace notebook service before executing `build/teardown.sql`, because the service uses the configured compute pool. Teardown removes the configured database, warehouse, compute pool, and roles.

The private Git-backed Workspace is not managed by these scripts. Delete it separately through Snowsight after the Snowflake objects have been removed and any intended repository changes have been committed and pushed.

## Documentation

- [MLOps with Snowflake ML](docs/mlops-with-snowflake-ml.md)
- [From Notebook to Production with Snowflake ML](docs/implementing-mlops-on-snowflake.md)

## Important limitation

The generated credit data and model workflow are technical teaching assets. Protected characteristics and direct proxies are intentionally excluded. A real credit-risk implementation requires independent model-risk management, fairness testing, explainability, validation, approval, and applicable regulatory controls.