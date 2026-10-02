# Workshop demo runbook

This is the presenter contract for the 90-minute, 25-slide workshop. It maps the four timed demos to current assets and later increments. It does not claim any demonstration has run successfully.

Master presentation: [MLOps That Runs on Snowflake](https://docs.google.com/presentation/d/1kzQ48NUvei10eGSe7gbgXzJO61okbe-o2SOyqfH6pTE/edit).

Do not run this disposable workload in Snowhouse.

## Workshop defaults

- Keep 25 core slides and four demo slots of 6, 5, 6 and 5 minutes.
- Keep all three interactive notebooks. Manual selection and holdout gates stay presenter-controlled.
- Disposable demo schemas: `RAW`, `DEV`, `TEST` (**Pre-Prod**), `PROD`, `CONTROL`.
- Production recommendation remains separate databases in one account.
- Required serving path is warehouse batch. Online services, Gateways, async batch jobs and exact-artefact copy are reference branches.
- Execute Code Bundles from a Workspace SQL file or task, never from a notebook cell.

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

Fallback: walk the specification and contract only. Never imply the command ran.

### Demo 3

1. Show a rejected candidate and an unchanged incumbent.
2. Show a separately approved candidate and its evidence identity.
3. Show the exact-version warehouse smoke test.
4. Change the serving selection, verify, then restore the previous compatible path.

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

## Current readiness

| Demo | Implemented | Statically tested | Target-executed | Timed / rehearsed | Fallback ready |
|---|---|---|---|---|---|
| 1 | Notebooks plus evidence handoff | 69 local tests passed | Inspected only | No | Conceptual walkthrough |
| 2 | Payload, specification and inspect SQL | 69 local tests passed | Inspected only | No | Spec walkthrough |
| 3 | Approval and serving-selection functions | 69 local tests passed | Inspected only | No | State-diagram walkthrough |
| 4 | Replay, coverage and action contracts | 69 local tests passed | Inspected only | No | Evidence-contract walkthrough |

Confirmed 2026-10-02 via `snow sql -c sfseeurope-mstellwall-aws-us-west3` as `AGENT_USER` / `SYSADMIN` on `MSTELLWALL_AWS_US_WEST3`:
- Present: `CRISK_DEMO_DB`, schemas `RAW`/`DEV`/`TEST`/`PROD`/`CONTROL`/`DEV_FEATURE_STORE`, roles, warehouse `CRISK_DEMO_WH` (SUSPENDED), pool `CRISK_DEMO_POOL` (SUSPENDED), bootstrap source tables, reserved `PIPELINE_RUN` and `PROMOTION_DECISION`.
- Absent: models, experiments, datasets, Code Bundles, `TEST_FEATURE_STORE`, `PROD_FEATURE_STORE`, `SOURCE_RELEASE`, `PIPELINE_ATTEMPT`, `SERVING_SELECTION`, `PREDICTION_RECORD`.
- `CODE_BUNDLE_HISTORY` for `CRISK_DEMO_DB.DEV` compiled and returned no rows.

Never use the connected Snowhouse account. The IDE SQL tool routed to Snowhouse even when the demo connection name was supplied; use `snow sql -c sfseeurope-mstellwall-aws-us-west3` for this disposable demo.

## Authorisation boundary

Updating this runbook does not authorise bootstrap, Code Bundle execution, schedule activation, teardown, commits or pushes. Target rehearsal is increment 9 and remains separately authorised.
