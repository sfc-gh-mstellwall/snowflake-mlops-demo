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
| **Segment 2: Feature Store & Point-in-Time Datasets** | After **Slide 10** (`REUSE FEATURES AND PIN THE CONTRACT`) | `notebooks/02_credit_default_feature_engineering.ipynb` | `Entity("CREDIT_ACCOUNT")`, 3 tiled `FeatureView`s (`Feature.avg/max/sum/stddev`) + 3 Snowpark-derived `FeatureView`s registered as `V01`, and immutable `fs.generate_dataset()` with 90-day finality purge. |
| **Segment 3: Tracked Experiments, Holdout Gate & Lineage** | After **Slide 11** (`TRACE EVERY CANDIDATE END TO END`) | `notebooks/03_credit_default_model_experiment.ipynb` | `with exp.start_run():`, `Tuner` HPO trials, presenter holdout gate (`evaluate_holdout`), refit on `CREDIT_REFIT`, evaluation on `CREDIT_HELD_OUT`, and `exp.log_model()` with Dataset → Model Registry lineage. |
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

### Segment 2 — `notebooks/02_credit_default_feature_engineering.ipynb` (Stage 2: Prepare)

1. **Show Section 1 & Sections 3–5 (`FeatureStore` & 6 `V01` Feature Views):**
   - Show `Entity(name="CREDIT_ACCOUNT", join_keys=["ACCOUNT_ID"])`.
   - Highlight the combination of **declarative tiled Feature Views** (`ACCOUNT_AGGREGATION_FV`, `ACCOUNT_PAYMENT_FV`, `ACCOUNT_CONTACT_FV` using `Feature.avg`, `Feature.max`, `Feature.stddev`, `Feature.sum` at `1 day` granularity) and **Snowpark-derived Feature Views** (`ACCOUNT_PROFILE_FV`, `ACCOUNT_BALANCE_FV`, `ACCOUNT_DELINQUENCY_FV`), all registered with explicit version `V01`.
2. **Show Section 6 & 7 (Point-in-time spine cutoffs & `fs.generate_dataset`):**
   - Show the temporal split (`development_cutoff = "2025-07-01"`, `holdout_cutoff = "2026-01-01"`) with the 90-day finality filter (`OUTCOME_FINALITY_DATE < cutoff`).
   - Show `fs.generate_dataset(..., spine_timestamp_col="OBSERVATION_TS", join_method="cte")` producing immutable `CREDIT_DEVELOPMENT` and `CREDIT_VALIDATION` Datasets.
3. **Show Section 8 (Upstream lineage):**
   - Show `fs.load_feature_views_from_dataset(...)` and `.lineage(direction="upstream")` proving exact Feature View → Dataset provenance.

---

### Segment 3 — `notebooks/03_credit_default_model_experiment.ipynb` (Stage 3: Train & Screen in `DEV`)

1. **Show Section 1 (Loading immutable Datasets):**
   - Point out that Notebook 03 never queries `RAW` tables or re-computes features—it loads `CREDIT_DEVELOPMENT` and `CREDIT_VALIDATION` by exact version and keeps a Snowpark `training_sample` for Model Registry signature and lineage.
2. **Show Sections 6–9 (`ExperimentTracking` & `Tuner` HPO):**
   - Show `with exp.start_run(...):` logging parameters, holdout metrics, and candidate models (`LogisticRegression` vs. `HistGradientBoostingClassifier`), followed by bounded HPO trials via `Tuner` and `DataConnector.from_dataset()`.
3. **Show Sections 10–13 (Manual holdout gate, `CREDIT_REFIT`, `CREDIT_HELD_OUT` & lineage):**
   - Show how `CREDIT_REFIT` and `CREDIT_HELD_OUT` are materialised only after the candidate is selected, evaluated against segment support floors (`PRODUCT_CODE`, `ORIGINATION_CHANNEL`), and logged to the Model Registry with full upstream lineage (`refit_registered.lineage(direction="upstream")`).
   - State the core transition to Notebook 04: **"Logging a model in `DEV` is traceability, not production approval."**

---

### Segment 4 — `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` (Sections 1 & 2: Code Bundles & Approval)

1. **Show Cell 1 (Environment bindings table):**
   - Contrast `DEV` (`DEV_FEATURE_STORE`), `TEST` (`Pre-Prod` / `TEST_FEATURE_STORE`, `may_approve_future_prod_model = False`), and `PROD` (`PROD_FEATURE_STORE`, `may_change_live_serving = True`).
2. **Show Section 1 / Cell 3 (Loop 1 Pre-Prod validation & Loop 2 Prod candidate creation):**
   - Walk through how the shared `train_and_register_candidate()` function (invoked by `jobs/train.py` inside the Code Bundle) runs in `TEST` to validate the pipeline release (`approve_pipeline`) and then runs in `PROD` against `PROD_FEATURE_STORE` to register `CANDIDATE_PROD_R_2026_10_01` and write its 5-gate screening result (`accepted`) to `CONTROL.PIPELINE_ATTEMPT`.
   - Optionally open `deployment/06_environment_releases.sql` to show the `CREATE CODE BUNDLE` and `CREATE OR REPLACE TASK ... AS EXECUTE CODE BUNDLE ...` definitions.
3. **Show Section 2 / Cell 5 (Loop 3 Fail-Closed Activation & Accountable Owner Approval):**
   - Point out the first print output: calling `activate_serving()` before owner approval returns `rejected: no matching approve record in PROMOTION_DECISION`.
   - Show `record_promotion_decision()` executed under `CRISK_DEMO_PROD_OWNER`, writing the `'approve'` row into `CONTROL.PROMOTION_DECISION`.

---

### Segment 5 — `notebooks/04_credit_default_release_serving_and_monitoring.ipynb` (Sections 3, 4 & 5: Serving, Gateway Shadow/Split, Monitoring & Rollback)

1. **Show Section 3 / Cell 7 (Warehouse Batch Serving Default):**
   - Show `activate_serving(..., mode="BATCH", candidate_weight=100)` calling the owner's-rights `CONTROL.ACTIVATE_SERVING` procedure, which moves the `PRODUCTION` model alias and writes the active row to `CONTROL.SERVING_SELECTION`.
   - Show `run_warehouse_batch_scoring()` resolving `version("PRODUCTION")` from the Model Registry, scoring `RAW.SCORING_POPULATION` on the warehouse across pre-drift (`2025-10` to `2025-12`) and post-drift (`2026-01` to `2026-07`) months, and writing durable rows to `CONTROL.PREDICTION_RECORD`.
2. **Show Section 4 / Cell 9 (Online Reference Branch — Stable Gateway `SHADOW` vs. `SPLIT`):**
   - Show that attempting online `SHADOW` activation for challenger `v2` before `jobs/deploy_service.py` runs returns `rejected: candidate SPCS service has no SMOKE_TESTED receipt`.
   - Walk through the two Gateway specifications printed by the cell:
     - **Option A — Shadow Model (`type: shadow_traffic`, Preview):** `primary` (`v1`) continues serving `100%` of caller responses while `shadow` (`v2`) receives `10%` mirrored live requests—logged via `autocapture=True` and compared in a Gateway Model Monitor (`GATEWAY = ...`).
     - **Option B — Traffic Split (`type: traffic_split`, GA):** `90% v1 / 10% v2` canary to `100% v2` cutover.
3. **Show Section 5 / Cells 11 & 12 (Delayed 90-Day Outcomes, Drift Chart & Full-Path Rollback):**
   - Point out the 3-row replay table (`2026-02-15`, `2026-05-15`, `2026-09-01`) and the two side-by-side charts:
     - On `2026-02-15`, January 2026 score shift is already visible, but January 90-day outcomes are still `PENDING` (`RECOMMENDED_ACTION = investigate`, not blind retrain).
     - By `2026-05-15` and `2026-09-01`, the post-`2026-01` cohorts reach 90-day `FINAL` maturity, confirming accuracy degradation (`RECOMMENDED_ACTION = train_candidate`) while keeping June–July cohorts as `PENDING` rather than `0`.
   - Point out the final table in Cell 12: `record_operational_action()` records the governance action in `CONTROL.OPERATIONAL_ACTION`, and `recover_serving()` (`CALL CONTROL.RECOVER_SERVING('PROD')`) restores the prior `PRODUCTION` alias and marks the previous selection `RESTORED` and `ACTIVE = TRUE`.

---

## 4. Post-Demo Teardown

1. Shut down the Workspace notebook service so `CRISK_DEMO_POOL` is idle.
2. Open `build/99_teardown.sql` in a Workspace SQL editor and run it as `ACCOUNTADMIN` to drop `CRISK_DEMO_DB`, `CRISK_DEMO_WH`, `CRISK_DEMO_POOL`, and the four `CRISK_DEMO_*` roles.
