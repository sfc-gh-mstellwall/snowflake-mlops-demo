# Presentation & demo runbook

This runbook maps the MLOps story across the **18-slide standard presentation** ([MLOps That Runs on Snowflake — Standard Presentation](https://docs.google.com/presentation/d/1QDS-NzGTbERi2C-TlQ4kyTJxYTRkmM6cC4Bvgo08V-g/edit)), the preserved **25-slide workshop master** ([MLOps That Runs on Snowflake — Workshop Master](https://docs.google.com/presentation/d/1kzQ48NUvei10eGSe7gbgXzJO61okbe-o2SOyqfH6pTE/edit)), and the **4 Snowflake Workspace notebooks** (`notebooks/01` through `notebooks/04`).

Do not run this disposable workload in Snowhouse.

## Defaults

- **Four interactive Workspace notebooks:**
  1. `notebooks/01_credit_default_exploration.ipynb` — Stage 1: Explore (`RAW` contracts, grain, warmup, and 90-day delayed label finality).
  2. `notebooks/02_credit_default_feature_engineering.ipynb` — Stage 2: Prepare (`Entity("CREDIT_ACCOUNT")`, 6 `V01` Feature Views, and immutable `CREDIT_DEVELOPMENT` / `CREDIT_VALIDATION` Datasets).
  3. `notebooks/03_credit_default_model_experiment.ipynb` — Stage 3: Train & Screen in `DEV` (`ExperimentTracking`, `Tuner` HPO, manual holdout gates, refit on `CREDIT_REFIT`, evaluation on `CREDIT_HELD_OUT`, and `Model Registry` logging with lineage).
  4. `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` — Stages 4–7: Code Bundles & unattended candidate creation in `Pre-Prod` (`TEST`) and `PROD`, accountable owner approval (`PROMOTION_DECISION`), `ACTIVATE_SERVING` for **Warehouse Batch** (`SET ALIAS = PRODUCTION`) and **Online Gateway** (`SHADOW` vs. `SPLIT`), delayed 90-day ground-truth replay (`V_PREDICTION_OUTCOME_MATURITY`), and full-path rollback (`RECOVER_SERVING`).
- Disposable demo schemas: `RAW`, `DEV`, `TEST` (**Pre-Prod**), `PROD`, `CONTROL`, `DEV_FEATURE_STORE`, `TEST_FEATURE_STORE`, `PROD_FEATURE_STORE`.
- Production recommendation remains separate databases (`ML_DEV`, `ML_PREPROD`, `ML_PROD`) in one account.
- Default serving path is warehouse batch (`SET ALIAS = PRODUCTION`). Online SPCS services (`jobs/deploy_service.py` with `autocapture=True`) and Gateways (`type: shadow_traffic` Preview and `type: traffic_split` GA) are demonstrated alongside batch in Notebook 04.
- Tool boundary to state aloud: DCM declares scaffolding (schemas, roles, grants, suspended tasks, SQL procedures). The Snowflake CLI in CI performs release steps (`snow stage copy`, `snow sql -x` to create the release-specific bundle and call `EXECUTE CODE BUNDLE` / `CALL ACTIVATE_SERVING`). The Code Bundle (`jobs/train.py`, `jobs/deploy_service.py`) is the Python ML execution unit on a compute pool.

## Decision vocabulary

| Term | Meaning | Does not mean |
|---|---|---|
| Registration | A Registry version exists and is linked to evidence | The model may serve |
| Screening `accepted` | The candidate passed the frozen screening contract | Approval or live serving |
| Screening `rejected` | Evidence exists, candidate is not eligible | Incumbent changed or evidence deleted |
| `failed` | The attempt did not complete a valid candidate path | A fabricated model version |
| Approval | An accountable owner authorises a specific version | The serving selector already moved |
| Serving activation | Callers resolve that approved version | A new pipeline release |

Pre-Prod can approve a pipeline release. It cannot approve a Prod-trained model that does not yet exist.

## Slide-to-demo map

| Demo | Slides | Slot | Start | Stop | Visible evidence |
|---|---|---|---|---|---|
| 1: Trace a candidate | 10-12 | 6 min | After Feature/Dataset/Experiment objects exist | Before any Code Bundle or promotion claim | Pinned Feature Views, frozen Dataset, Experiment/refit/conclusion runs, exact Registry candidate |
| 2: Execute a bundle | 13-15 | 5 min | After an immutable release exists | Before live serving changes | Reviewed source, specification, environment identity, history, durable accepted/rejected/failed receipt |
| 3: Reject, promote, recover | 16-19 | 6 min | After two distinct candidates and an incumbent exist | Before outcome-monitor claims | Unchanged incumbent on rejection, separate approval, exact-candidate warehouse test, verified promotion and rollback |
| 4: Outcomes into action | 20-22 | 5 min | After durable predictions and a replay clock exist | Before inventing charts or scores | Prediction identity, delayed outcome, coverage, distinct drift and performance, recorded action |

## Presenter routes

### Demo 1

1. Open the Feature View versions created by notebook 02.
2. Open the immutable Dataset version handed to notebook 03.
3. Open the Experiment, then the selected, refit and conclusion runs.
4. Open the exact Registry candidate and show that registration is not approval.
   The later `src/credit_default/evidence.py` handoff records the same chain and
   explicitly keeps `approved` and `serving_active` false.

Fallback: if no target-executed records exist, label the walkthrough conceptual. Do not invent IDs.

### Demo 2

1. Inspect the reviewed source payload and `code_bundle.yml`.
2. Open the Workspace SQL file that creates or identifies the release-specific bundle.
3. Execute the bundle from that SQL file, not a notebook cell.
4. Inspect `CODE_BUNDLE_HISTORY` and the durable pipeline-run receipt.

Presenter note: in production, steps 1–2 are CI using the Snowflake CLI on merge (`snow stage copy`, then `snow sql -x` to create the bundle). Step 3 in Prod is a DCM-defined task that stays suspended until verified.

Fallback: walk the specification and contract only. Never imply the command ran.

### Demo 3

1. Show a rejected candidate and an unchanged incumbent.
2. Show a separately approved candidate and its evidence identity.
3. Show the exact-version warehouse smoke test.
4. Change the serving selection, verify, then restore the previous compatible path.

Presenter note: approval is a Snowflake record; CI carries out activation only after reading it. For the online branch, the Gateway stays fixed and a new service per candidate is routed with `ALTER GATEWAY`. Not demonstrated.

Fallback: walk the state diagram without invented scores or deployment claims.

### Demo 4

1. Trace one prediction ID to its account/observation key and model version.
2. Advance the historical replay clock rather than regenerating bootstrap.
3. Show pending versus final labels, coverage and unmatched records as unknown.
4. Keep drift separate from performance, then record an action that does not mutate the incumbent.

Fallback: walk the evidence contract without fabricated monitor charts.

## Timing and contingency

Opening and architecture, slides 1-8: 17 minutes. Features and Demo 1, slides 9-12: 16 minutes. Packaging and Demo 2, slides 13-15: 14 minutes. Release and Demo 3, slides 16-18: 13 minutes. Serving, monitoring and Demo 4, slides 19-22: 15 minutes. Ownership and close, slides 23-25: 5 minutes. Protected questions and demo contingency: 10 minutes.

If a live bundle exceeds its slot, show an explicitly identified prior completed run and describe the current run honestly.

## Showcase asset map

| Demo / Stage | Standard Deck Slides | Primary Showcase Assets |
|---|---|---|
| 1: Explore, Features & Candidate Lineage | Slides 4–5, 10–11 | `notebooks/01_credit_default_exploration.ipynb`, `notebooks/02_credit_default_feature_engineering.ipynb`, `notebooks/03_credit_default_model_experiment.ipynb` |
| 2: Code Bundles & Unattended Candidate Creation | Slides 8, 12 | `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` (Section 1), `jobs/train.py`, `src/credit_default/training.py`, `deployment/05_code_bundle.sql`, `deployment/06_environment_releases.sql` |
| 3: Owner Approval, Batch Alias & Gateway (`SHADOW` / `SPLIT`) | Slides 14–15 | `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` (Sections 2–4), `jobs/deploy_service.py`, `src/credit_default/approval.py`, `deployment/04_control_contracts.sql` (`ACTIVATE_SERVING`, `RECOVER_SERVING`) |
| 4: Delayed 90-Day Outcomes, Drift & Rollback | Slides 16–17 | `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` (Section 5), `src/credit_default/monitoring.py`, `deployment/07_monitoring.sql` (`V_PREDICTION_OUTCOME_MATURITY`) |

Confirmed 2026-10-02 via `snow sql -c sfseeurope-mstellwall-aws-us-west3` as `AGENT_USER` / `SYSADMIN` on `MSTELLWALL_AWS_US_WEST3`:
- Present: `CRISK_DEMO_DB`, schemas `RAW`/`DEV`/`TEST`/`PROD`/`CONTROL`/`DEV_FEATURE_STORE`, roles, warehouse `CRISK_DEMO_WH` (SUSPENDED), pool `CRISK_DEMO_POOL` (SUSPENDED), bootstrap source tables, reserved `PIPELINE_RUN` and `PROMOTION_DECISION`.
- Absent: models, experiments, datasets, Code Bundles, `TEST_FEATURE_STORE`, `PROD_FEATURE_STORE`, `SOURCE_RELEASE`, `PIPELINE_ATTEMPT`, `SERVING_SELECTION`, `PREDICTION_RECORD`.
- `CODE_BUNDLE_HISTORY` for `CRISK_DEMO_DB.DEV` compiled and returned no rows.

Never use the connected Snowhouse account. The IDE SQL tool routed to Snowhouse even when the demo connection name was supplied; use `snow sql -c sfseeurope-mstellwall-aws-us-west3` for this disposable demo.

## Authorisation boundary

Updating this runbook does not authorise bootstrap, Code Bundle execution, schedule activation, teardown, commits or pushes. Target rehearsal is increment 9 and remains separately authorised.
