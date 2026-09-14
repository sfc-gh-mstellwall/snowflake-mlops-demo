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
tests/             Local renderer and safety tests
project.yaml       Portable names, compute, data, and model settings
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

## Configure and render

Review `project.yaml` and keep the safety convention that `project.prefix` ends in `_DEMO`. Every destructive account object must begin with that exact prefix.

Install the two local development dependencies in an isolated environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

Render account-ready SQL:

```bash
.venv/bin/python scripts/render_sql.py \
  --config project.yaml \
  --output-dir build
```

Review the generated files in `build/` before executing them:

```text
build/bootstrap.sql
build/verify_data.sql
build/inventory.sql
build/teardown.sql
```

Run `bootstrap.sql` in the intended demonstration account with a role that can create roles, databases, warehouses, compute pools, and account-level task grants. Do not run it in an account where the configured names are used by non-demo resources.

After bootstrap, run `verify_data.sql`. Continue to notebook development only when `PHASE_1_STATUS` is `PASS` and the visible population checks are reasonable.

## Teardown

Run `inventory.sql` and review every listed object before executing `teardown.sql`. Teardown removes the configured database, warehouse, compute pool, and roles.

Private Git-backed Workspaces are created interactively through Snowsight and are not managed by these scripts. Delete any Workspace created for the demo separately.

## Documentation

- [MLOps with Snowflake ML](docs/mlops-with-snowflake-ml.md)
- [From Notebook to Production with Snowflake ML](docs/implementing-mlops-on-snowflake.md)

## Important limitation

The generated credit data and model workflow are technical teaching assets. Protected characteristics and direct proxies are intentionally excluded. A real credit-risk implementation requires independent model-risk management, fairness testing, explainability, validation, approval, and applicable regulatory controls.