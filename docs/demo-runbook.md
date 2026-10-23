# Presentation & Demo Runbook

This runbook walks through setting up and presenting the credit-default MLOps showcase alongside the **18-slide standard presentation**:

- **Standard Presentation (18 slides):** [MLOps That Runs on Snowflake — Standard Presentation](https://docs.google.com/presentation/d/1QDS-NzGTbERi2C-TlQ4kyTJxYTRkmM6cC4Bvgo08V-g/edit)
- **Presentation Outline & Speaker Notes:** [`presentation_outline.md`](../presentation_outline.md)
- **Preserved Workshop Master (25 slides):** [MLOps That Runs on Snowflake — Workshop Master](https://docs.google.com/presentation/d/1kzQ48NUvei10eGSe7gbgXzJO61okbe-o2SOyqfH6pTE/edit)

Do not run this disposable workload in Snowhouse. Use your dedicated demo account (`sfseeurope-mstellwall-aws-us-west3`).

---

## 1. Pre-Demo Environment Setup (Run Once Before Presenting)

1. **Create or verify the compute pool** (as `ACCOUNTADMIN` in a Workspace SQL file):
   - Run `00_workspace_setup.sql` to ensure `CRISK_DEMO_POOL` exists.
2. **Render the SQL templates**:
   - Open `scripts/render_sql.py` in the Git-backed Workspace (connected to `CRISK_DEMO_POOL` on Container Runtime CPU 2.9) and click **Run** to generate `build/*.sql`.
3. **Bootstrap the demo database, roles, synthetic data, and control contracts**:
   - Execute `build/01_bootstrap.sql` (creates `CRISK_DEMO_DB`, roles `CRISK_DEMO_{DEVELOPER,ENGINEER,PROD_OWNER,SERVICE}`, warehouse `CRISK_DEMO_WH`, schemas `RAW`, `DEV`, `TEST`, `PROD`, `CONTROL`, `DEV_FEATURE_STORE`, and 30 months of synthetic credit observations with a controlled drift regime starting `2026-01-01`).
   - Execute `build/03_verify_data.sql` and confirm `PHASE_1_STATUS = 'PASS'`.
   - Execute `build/04_control_contracts.sql` (creates `TEST_FEATURE_STORE` and `PROD_FEATURE_STORE`, control tables `SOURCE_RELEASE`, `ENVIRONMENT_DEPLOYMENT`, `PIPELINE_ATTEMPT`, `SERVING_SELECTION`, `SERVICE_DEPLOYMENT`, and the owner's-rights stored procedures `CONTROL.ACTIVATE_SERVING` and `CONTROL.RECOVER_SERVING`).
   - Execute `build/07_monitoring.sql` (creates `PREDICTION_RECORD`, `OPERATIONAL_ACTION`, and the delayed-outcome maturity view `CONTROL.V_PREDICTION_OUTCOME_MATURITY`).
4. **Pre-run the 4 notebooks** (optional, recommended for a 30–45 minute presentation):
   - Pre-execute Notebooks `01`, `02`, `03`, and `04` in your Workspace so all cell tables and charts are rendered and ready to walk through live without waiting on training or dataset generation.

---

## 2. Slide-to-Code Walkthrough Map (18-Slide Standard Deck)

| Demo Segment | When to Switch to Code | Notebook / File | Key Takeaway Shown Live |
|---|---|---|---|
| **Segment 1: Source Contracts & Delayed Labels** | After **Slide 5** (`FOLLOW ONE CONTINUOUS MLOPS LOOP`) or **Slide 10** | `notebooks/01_credit_default_exploration.ipynb` | Grain/key verification (`%%sql`), 365-day lookback coverage, and why 90-day labels are `PENDING` near the cutoff (`OUTCOME_FINALITY_DATE`). |
| **Segment 2: Feature Engineering & Feature Store Registration** | After **Slide 10** (`REUSE FEATURES AND PIN THE CONTRACT`) | `notebooks/02_credit_default_feature_engineering.ipynb` | `Entity("CREDIT_ACCOUNT")`, 3 tiled `FeatureView`s (`Feature.avg/max/sum/stddev`) + 3 Snowpark-derived `FeatureView`s registered as `V01` in `DEV_FEATURE_STORE`, raw-vs-derived spot checks, and `fs.retrieve_feature_values()`. |
| **Segment 3: Feature Discovery, Immutable Datasets, Tracked Experiments & Lineage** | After **Slide 11** (`TRACE EVERY CANDIDATE END TO END`) | `notebooks/03_credit_default_model_experiment.ipynb` | Feature Store discovery (`fs.list_entities()`, `fs.list_feature_views()`), feature selection, 90-day finality embargo spines, immutable `fs.generate_dataset()` (`CREDIT_DEVELOPMENT`, `CREDIT_VALIDATION`), `with exp.start_run():`, `Tuner` HPO trials, frozen held-out gates, refit on `CREDIT_REFIT`, evaluation on `CREDIT_HELD_OUT`, and `exp.log_model()` with Dataset → Model Registry lineage. |
| **Segment 4: Code Bundles, Pre-Prod vs. Prod & Owner Approval** | After **Slide 12** (`ORCHESTRATE WITH CLEAR TOOL BOUNDARIES`) or **Slide 14** | `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` (Sections 1–2) & `jobs/train.py` | Same code bundle runs in `Pre-Prod` (`TEST` — Gate 1 pipeline validation) and `PROD` (`PROD_FEATURE_STORE` — Loop 2 candidate creation). `ACTIVATE_SERVING` fails closed until `PROD_OWNER` writes `'approve'` to `PROMOTION_DECISION` (Gate 2). |
| **Segment 5: Batch Alias vs. Gateway (`SHADOW` / `SPLIT`), Drift & Rollback** | After **Slide 15** (`BATCH BY DEFAULT, GATEWAY FOR ONLINE`) & **Slide 16** | `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` (Sections 3–5) & `jobs/deploy_service.py` | Warehouse batch scoring via `SET ALIAS = PRODUCTION` into `PREDICTION_RECORD`; online Gateway `shadow_traffic` (Preview) vs. `traffic_split` (GA); 90-day outcome replay (`PENDING` never treated as `0`); and full-path rollback (`RECOVER_SERVING`). |

---

## 3. Step-by-Step Presenter Walkthrough

### Segment 1 — `notebooks/01_credit_default_exploration.ipynb` (Stage 1: Explore)

1. **Show Section 1 (`source_contract` SQL cell & grain checks):**
   - Point out that every `RAW` table is checked for primary-key uniqueness, orphan foreign keys, and null counts before any feature is written.
2. **Show Section 2 & 3 (365-day lookback & sample trajectories):**
   - Highlight the 4 sample accounts (2 defaulted, 2 current) showing rising credit utilisation and days-past-due prior to default.
3. **Show Section 4 (Delayed 90-day label finality):**
   - Emphasise `OUTCOME_STATUS` (`FINALISED` vs. `PENDING`): because credit default is measured over a 90-day window (`OUTCOME_FINALITY_DATE`), observations within 90 days of a cutoff have incomplete outcomes and must be purged from training spines rather than treated as non-default (`0`).

---

### Segment 2 — `notebooks/02_credit_default_feature_engineering.ipynb` (Stage 2: Prepare — Feature Store)

1. **Show Section 1 (`CREDIT_ACCOUNT` Entity):**
   - Show `Entity(name="CREDIT_ACCOUNT", join_keys=["ACCOUNT_ID"])` and explain how the shared entity key lets the Feature Store join Feature Views built from monthly, daily, and event-level sources via point-in-time `ASOF` timestamp matching.
2. **Show Sections 2–5 (Iterative Feature Development, Spot Checks & 6 `V01` Feature Views):**
   - Show how each source table is introduced once where first needed and previewed with `.limit(10)`.
   - Highlight the combination of **declarative tiled Feature Views** (`ACCOUNT_AGGREGATION_FV`, `ACCOUNT_PAYMENT_FV`, `ACCOUNT_CONTACT_FV` using `Feature.avg`, `Feature.max`, `Feature.stddev`, `Feature.sum` at `1 day` granularity) and **Snowpark-derived Feature Views** (`ACCOUNT_PROFILE_FV`, `ACCOUNT_BALANCE_FV`, `ACCOUNT_DELINQUENCY_FV`), all registered with explicit version `V01` in `DEV_FEATURE_STORE`.
3. **Show Section 6 (`fs.retrieve_feature_values()` verification):**
   - Show point-in-time feature retrieval across all six registered `V01` Feature Views for the 4 sample accounts before handing off to Notebook 03.

---

### Segment 3 — `notebooks/03_credit_default_model_experiment.ipynb` (Stage 2 → 3: Feature Selection, Immutable Datasets & Tracked Experiments in `DEV`)

1. **Show Sections 1 & 2 (Feature Store Discovery & Feature Selection):**
   - Show how the model developer connects to `DEV_FEATURE_STORE`, discovers registered Entities and Feature Views (`fs.list_entities()`, `fs.list_feature_views()`), inspects the 41-feature catalog, and selects the six `V01` Feature Views and predictor lists (`numeric_features` and `categorical_features`).
2. **Show Sections 3 & 4 (Embargoed Spines, `fs.generate_dataset()` & Upstream Lineage):**
   - Show the temporal split (`development_cutoff = "2025-07-01"`, `holdout_cutoff = "2026-01-01"`) with the 90-day finality filter (`OUTCOME_FINALITY_DATE < cutoff`).
   - Show `fs.generate_dataset(..., spine_timestamp_col="OBSERVATION_TS", join_method="cte")` producing immutable `CREDIT_DEVELOPMENT` and `CREDIT_VALIDATION` Datasets, verifying zero future feature leakage (`*_TS <= OBSERVATION_TS`), and inspecting provenance with `development_dataset.lineage(direction="upstream")`.
3. **Show Sections 5–7 (`ExperimentTracking`, `Tuner` HPO & candidate selection):**
   - Show `with exp.start_run(...):` logging parameters, validation metrics, and one baseline `HistGradientBoostingClassifier`, followed by four tracked HPO trials via `Tuner` and `DataConnector.from_dataset()`, and selection of the run with the highest validation average precision.
4. **Show Sections 8–9 (Frozen gates, `CREDIT_REFIT`, `CREDIT_HELD_OUT` & lineage):**
   - Show how `CREDIT_REFIT` and `CREDIT_HELD_OUT` are materialised only after the candidate is selected, evaluated against segment support floors (`PRODUCT_CODE`, `ORIGINATION_CHANNEL`), and logged to the Model Registry with full upstream lineage (`refit_registered.lineage(direction="upstream")`).
   - State the core transition to Notebook 04: **"Logging a model in `DEV` is traceability, not production approval."**

---

### Segment 4 — `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` (Sections 1 & 2: Code Bundles & Approval)

1. **Show Cell 1 (`setup_session_and_environment_bindings`):**
   - Contrast `DEV` (`DEV_FEATURE_STORE`), `TEST` (`Pre-Prod` / `TEST_FEATURE_STORE`, `may_approve_future_prod_model = False`), and `PROD` (`PROD_FEATURE_STORE`, `may_change_live_serving = True`).
2. **Show Section 1 / Cells 3–5 (Loop 1 Pre-Prod validation & Loop 2 Prod candidate creation):**
   - Walk through recording `R_2026_10_01` (`Cell 3`), validating the pipeline release in `TEST` (`Cell 4`), and running the same reviewed Code Bundle in `PROD` against `PROD_FEATURE_STORE` (`Cell 5`) to register `CANDIDATE_PROD_R_2026_10_01` and write its 5-gate screening result (`accepted`) to `CONTROL.PIPELINE_ATTEMPT`.
   - Optionally open `deployment/06_environment_releases.sql` to show the `CREATE CODE BUNDLE` and `CREATE OR REPLACE TASK ... AS EXECUTE CODE BUNDLE ...` definitions.
3. **Show Section 2 / Cells 7–8 (Loop 3 Fail-Closed Activation & Accountable Owner Approval):**
   - Point out `Cell 7`: calling `activate_serving()` before owner approval returns `rejected: no matching approve record in PROMOTION_DECISION`.
   - Show `Cell 8`: `record_promotion_decision()` executed under `CRISK_DEMO_PROD_OWNER`, writing the `'approve'` row into `CONTROL.PROMOTION_DECISION`.

---

### Segment 5 — `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` (Sections 3, 4 & 5: Serving, Gateway Shadow/Split, Monitoring & Rollback)

1. **Show Section 3 / Cells 10–11 (Warehouse Batch Serving Default):**
   - Show `Cell 10`: `activate_serving(..., mode="BATCH", candidate_weight=100)` calling the owner's-rights `CONTROL.ACTIVATE_SERVING` procedure, which moves the `PRODUCTION` model alias and writes the active row to `CONTROL.SERVING_SELECTION`.
   - Show `Cell 11`: `run_warehouse_batch_scoring()` resolving `version("PRODUCTION")` from the Model Registry, scoring `RAW.SCORING_POPULATION` on the warehouse across pre-drift (`2025-10` to `2025-12`) and post-drift (`2026-01` to `2026-07`) months, and writing durable rows to `CONTROL.PREDICTION_RECORD`.
2. **Show Section 4 / Cells 13–14 (Online Reference Branch — Stable Gateway `SHADOW` vs. `SPLIT`):**
   - Show `Cell 13`: attempting online `SHADOW` activation for challenger `v2` before `jobs/deploy_service.py` runs returns `rejected: candidate SPCS service has no SMOKE_TESTED receipt`.
   - Walk through the two Gateway specifications printed by `Cell 14`:
     - **Option A — Shadow Model (`type: shadow_traffic`, Preview):** `primary` (`v1`) continues serving `100%` of caller responses while `shadow` (`v2`) receives `10%` mirrored live requests—logged via `autocapture=True` and compared in a Gateway Model Monitor (`GATEWAY = ...`).
     - **Option B — Traffic Split (`type: traffic_split`, GA):** `90% v1 / 10% v2` canary to `100% v2` cutover.
3. **Show Section 5 / Cells 16–19 (Delayed 90-Day Outcomes, Drift Chart & Full-Path Rollback):**
   - Point out the 3-row replay table (`Cell 16`: `2026-02-15`, `2026-05-15`, `2026-09-01`), the cohort maturity view (`Cell 17`), and the two side-by-side charts (`Cell 18`):
     - On `2026-02-15`, January 2026 score shift is already visible, but January 90-day outcomes are still `PENDING` (`RECOMMENDED_ACTION = investigate`, not blind retrain).
     - By `2026-05-15` and `2026-09-01`, the post-`2026-01` cohorts reach 90-day `FINAL` maturity, confirming accuracy degradation (`RECOMMENDED_ACTION = train_candidate`) while keeping June–July cohorts as `PENDING` rather than `0`.
   - Point out the final cell (`Cell 19`): `record_operational_action()` records the governance action in `CONTROL.OPERATIONAL_ACTION`, and `recover_serving()` (`CALL CONTROL.RECOVER_SERVING('PROD')`) restores the prior `PRODUCTION` alias and marks the previous selection `RESTORED` and `ACTIVE = TRUE`.

---

## 4. Post-Demo Teardown

1. Shut down the Workspace notebook service so `CRISK_DEMO_POOL` is idle.
2. Open `build/99_teardown.sql` in a Workspace SQL editor and run it as `ACCOUNTADMIN` to drop `CRISK_DEMO_DB`, `CRISK_DEMO_WH`, `CRISK_DEMO_POOL`, and the four `CRISK_DEMO_*` roles.
