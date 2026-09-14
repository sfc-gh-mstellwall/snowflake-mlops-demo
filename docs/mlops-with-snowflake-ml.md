# MLOps with Snowflake ML

*An introduction to the machine learning operations lifecycle and how Snowflake supports it*

## 1. Why MLOps matters

Training a model is only one part of a production machine learning system. The surrounding work includes preparing data, reproducing experiments, deploying predictions, monitoring behaviour, controlling access, and deciding when a model should be replaced or retired. *Hidden Technical Debt in Machine Learning Systems* remains a useful foundation for this idea: model code is often a small part of the complete system, while data dependencies, configuration, serving, and monitoring create much of its complexity ([Sculley et al., 2015](https://papers.nips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html)).

**MLOps**, or Machine Learning Operations, applies software-engineering and operational practices to this wider system. It combines version control, automation, testing, deployment, and observability with concerns specific to ML: training data, feature consistency, experiment evidence, model performance, delayed ground truth, and responsible use.

There is no single universally adopted MLOps standard. Modern sources provide complementary perspectives. Kreuzberger, Kühl and Hirschl define a vendor-neutral architecture and role model ([IEEE Access, 2023](https://doi.org/10.1109/ACCESS.2023.3262138)); Paleyes, Urma and Lawrence examine deployment challenges observed in practice ([ACM Computing Surveys, 2022](https://doi.org/10.1145/3533378)); ISO/IEC 5338:2023 extends the view across the AI system lifecycle; and NIST AI RMF structures risk work around **Govern, Map, Measure, and Manage** ([ISO/IEC 5338](https://www.iso.org/standard/81118.html); [NIST AI RMF](https://doi.org/10.6028/NIST.AI.100-1)). Google's practitioner guidance remains influential for CI/CD and continuous training, but represents a cloud-provider perspective rather than a formal standard ([Google Cloud](https://cloud.google.com/resources/mlops-whitepaper)).

## 2. The MLOps lifecycle

MLOps is a loop rather than a one-way deployment process. Production evidence feeds new development, while governance and ownership apply throughout.

| Stage | Purpose | Typical questions |
|---|---|---|
| Data and features | Create reliable, reusable model inputs | Which data and feature versions were used? Were features point-in-time correct? |
| Experimentation | Compare features, algorithms, and parameters | Which run performed best, and can it be reproduced? |
| Training | Execute training at the required scale | Does the workload need a warehouse, multiple CPUs, or GPUs? |
| Registration | Create a governed model version | What signature, dependencies, metrics, task, and owner belong to it? |
| Inference | Generate predictions at the required latency and volume | Is scoring batch, asynchronous at scale, or real time? |
| Monitoring | Detect operational, drift, and performance changes | Are inputs changing? Are predictions still correct once labels arrive? |
| Governance and lineage | Control access and preserve evidence | What trained the model? Who can use it? What depends on it? |
| Promotion and retirement | Introduce and remove versions safely | How is a challenger evaluated, approved, rolled back, and retired? |

Several distinctions are important. Drift does not necessarily mean accuracy has fallen, and accuracy can fall without obvious input drift. Performance monitoring therefore requires ground-truth outcomes, not only input statistics. Similarly, automation is not maturity by itself: approval criteria, rollback, incident ownership, and retirement remain organisational decisions. Recent research identifies collaboration, governance, monitoring, and data management as core MLOps practices alongside automation ([Zarour et al., 2025](https://doi.org/10.1016/j.infsof.2025.107733)).

## 3. Snowflake ML architecture

Snowflake can run much of this lifecycle where governed data already resides. Virtual warehouses provide SQL and Snowpark execution. Snowpark Container Services (SPCS) provides containerised CPU and GPU compute for training, jobs, and model services. The Online Feature Store uses managed Snowflake Postgres for low-latency feature retrieval. These components reduce external data movement, but do not eliminate materialisation: Datasets create snapshots, models store artefacts, online features are synchronised, and monitoring retains operational data ([Snowflake ML overview](https://docs.snowflake.com/en/developer-guide/snowflake-ml/overview)).

A typical custom-model path is:

> Source tables → feature view → Dataset or training set → Experiment run → Model Registry version → batch inference or model service → predictions and ground truth → model monitor.

Not every model needs every component. The architecture should match the model's risk, scale, latency, and operating requirements.

### 3.1 Development, features, and reproducible data

**Notebooks in Workspaces** provide the primary interactive development environment. On Container Runtime, data scientists can combine SQL, Snowpark, and Python with CPU, GPU, or multi-node compute. Teams can use Snowflake runtime images or register a **Custom Runtime Environment** built from a Snowflake base image when package control, security scanning, and reproducibility require a governed image ([Container Runtime](https://docs.snowflake.com/en/developer-guide/snowflake-ml/container-runtime-ml); [Custom Runtime Images](https://docs.snowflake.com/en/developer-guide/snowflake-ml/custom-runtime-images)). The same notebook environment is available through **Remote Development** in Visual Studio Code or Cursor; this changes the authoring experience without changing the deployment model ([Remote Development](https://docs.snowflake.com/en/user-guide/vscode-ext-remote-development)).

The **Feature Store** creates a contract between feature engineering, training, and inference. Entities define the subject and join keys, while versioned feature views encapsulate transformations. Managed feature views use dynamic tables; external feature views register tables maintained by another pipeline such as dbt. Time-aware feature views support point-in-time retrieval, reducing leakage from future information ([Feature Store](https://docs.snowflake.com/en/developer-guide/snowflake-ml/feature-store/overview)).

The **Online Feature Store** can reuse registered definitions for low-latency retrieval, reducing training/serving skew. Parity still depends on consistent versions, preprocessing, timestamps, freshness, time zones, and request overrides. The real-time inference integration with the Postgres-backed online store is Preview and should be evaluated accordingly ([online features](https://docs.snowflake.com/en/developer-guide/snowflake-ml/feature-store/online-feature-store); [real-time integration](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/real-time-inference-rest-api#label-real-time-inference-online-feature-store-integration)).

**Datasets** store immutable, versioned Parquet snapshots for reproducible training and testing. They can feed pandas, PyTorch, TensorFlow, or Snowpark ML. `read.to_snowpark_dataframe()` reads the materialised Dataset version as a Snowpark DataFrame, while `read.files()` and `read.filesystem()` provide direct `fsspec` access for custom readers such as PyArrow or Dask ([Datasets](https://docs.snowflake.com/en/developer-guide/snowflake-ml/dataset)).

Feature transformation can use in-memory open-source preprocessors, warehouse-based `snowflake.ml.modeling.preprocessing`, or Ray processing on Container Runtime, depending on scale and library needs ([feature engineering](https://docs.snowflake.com/en/developer-guide/snowflake-ml/transform-data)). The **Distributed Partition Function** is complementary when custom Python processing naturally separates by a DataFrame key or staged file; it is not a Feature Store replacement and requires an explicit output contract ([DPF](https://docs.snowflake.com/en/developer-guide/snowflake-ml/process-data-across-partitions)).

### 3.2 Experiments, training, and registration

**Snowflake ML Experiments** records parameters, metrics, and artefacts for each run, making candidate comparison reproducible. Completed runs are immutable, and callbacks support common frameworks such as XGBoost, LightGBM, and Keras. When a model is registered with `exp.log_model()` during an active run, Snowflake links the Experiment and model version; this relationship is visible in the Experiment UI and as an `EXPERIMENT → MODEL` lineage edge through `GET_LINEAGE` ([Experiments](https://docs.snowflake.com/en/developer-guide/snowflake-ml/experiments); [GET_LINEAGE](https://docs.snowflake.com/en/sql-reference/functions/get_lineage-snowflake-core)).

Training can scale in different ways: distributed estimators train one large model; Many Model Training trains independent models per partition; and the `Tuner` API evaluates multiple hyperparameter configurations ([distributed training](https://docs.snowflake.com/en/developer-guide/snowpark-ml/reference/latest/distributors); [Many Model Training](https://docs.snowflake.com/en/developer-guide/snowflake-ml/train-models-across-partitions); [HPO](https://docs.snowflake.com/en/developer-guide/snowflake-ml/container-hpo)). **ML Jobs** turns Python functions or projects into repeatable workloads on compute pools, suitable for schedulers and external orchestrators ([ML Jobs](https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-jobs/overview)).

The **Model Registry** stores immutable, schema-level model versions regardless of where training occurred. A version can include signatures, dependencies, metrics, task metadata, comments, and tags. `USAGE` permits warehouse inference; `READ` additionally supports SPCS inference and metadata access. Strict dependency reproducibility requires governed `pip_requirements` or `conda_dependencies`; when exact versions must remain exact, disable dependency relaxation with `options={"relax_version": False}` ([Model Registry](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview)). Registry explainability can calculate SHAP values for supported model types and is currently in Preview ([explainability](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/model-explainability)).

### 3.3 Inference and operations

Inference should be selected by latency, volume, data shape, and operational ownership ([inference overview](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/inference-overview)).

- **Native warehouse inference** fits models that can execute within warehouse constraints and integrates naturally with SQL pipelines, Snowpark, dbt, Tasks, and Dynamic Tables. SQL uses `MODEL(...)!<method>()`; Python uses `ModelVersion.run()`. Incremental inference in a Dynamic Table requires an `IMMUTABLE` model method ([native inference](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/native-batch-inference-sql)).
- **Job-based batch inference** uses `run_batch()` and SPCS for large asynchronous workloads. It supports millions or billions of structured rows supplied through a query or Snowpark DataFrame, as well as unstructured files such as images, audio, and video ([batch inference jobs](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/batch-inference-jobs)).
- **Real-time inference** deploys a Registry model as a managed, autoscaling HTTP service on CPU or GPU SPCS compute. Snowflake manages the serving infrastructure, so teams do not need to build their own Kubernetes deployment or serving-container stack ([real-time inference](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/real-time-inference-rest-api)).

Monitoring has two complementary patterns. A **model version monitor** evaluates one model version using a prepared source table or view containing predictions, timestamps, features, and optional ground truth. A **Gateway monitor** compares services receiving traffic through a Gateway, for example in a champion/challenger rollout ([model observability](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/model-observability); [Gateway monitoring](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/gateway-monitor-and-ab-testing)).

**Auto Capture** can record supported requests and responses for an individual service without a Gateway. Failed requests capture no request or response data, and other size, throughput, and model-type limitations mean it should supplement application telemetry rather than replace it. A Gateway monitor consumes captures directly. To use direct-service captures with a model version monitor, first flatten and type them into the named table or view required as `SOURCE` ([Auto Capture](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/auto-capture-inference-logs); [`CREATE MODEL MONITOR`](https://docs.snowflake.com/en/sql-reference/sql/create-model-monitor)).

### 3.4 Governance, lineage, and controlled change

**ML Lineage** connects source tables and stages, feature views, Datasets, Experiment runs that log models, model versions, and deployed services. It supports reproducibility and impact analysis: teams can identify what data and experiment contributed to a model and which models depend on an upstream object. The exact edges depend on how artefacts are created; for example, `exp.log_model()` establishes the Experiment-to-model relationship ([ML Lineage](https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-lineage); [Experiments](https://docs.snowflake.com/en/developer-guide/snowflake-ml/experiments)).

Governance combines data controls with model controls. Source and result tables retain their masking, row-access, and other data policies. Models use `USAGE`, `READ`, and `OWNERSHIP` privileges and can carry tags and metadata for ownership, purpose, status, and classification. Horizon Catalog provides the wider discovery and governance context ([Snowflake Horizon](https://docs.snowflake.com/en/user-guide/snowflake-horizon)).

Tasks and Task Graphs can schedule training and inference. A **Gateway** provides a stable online endpoint and can split traffic between services. Shadow traffic copies selected requests to a challenger while callers receive only the primary response, allowing representative evaluation before the challenger becomes user-facing ([Task Graphs](https://docs.snowflake.com/en/developer-guide/snowflake-python-api/snowflake-python-managing-tasks); [Gateways](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/stable-endpoints-api-reference)). Thresholds, approval, rollback, and retirement remain controls that the organisation must define.

## 4. A minimum viable production path

For a team's first production model, the simplest useful path is usually batch-oriented:

1. Develop in a Notebook in a Git-backed Workspace, then move reusable logic into tested Python modules.
2. Create point-in-time-correct features and an immutable training Dataset.
3. Record the training run in Experiments and register the approved model version with its signature, strict dependencies, metrics, and task metadata.
4. Run warehouse batch inference through SQL or `ModelVersion.run()` and persist prediction IDs and timestamps.
5. Join predictions to delayed ground truth and create a model version monitor.
6. Schedule the pipeline with a Task Graph and assign explicit production ownership, alerts, rollback, and retirement rules.

Real-time services, online features, Gateways, and distributed batch jobs should be added when their latency or scale benefits justify their additional operational controls.

## 5. Conclusion

Snowflake ML provides integrated capabilities across the MLOps lifecycle, but integration does not remove operating-model decisions. Teams must still define the production artefact, dependency policy, execution identity, promotion method, monitoring data, approval gates, and accountable owner.

The companion paper, *Implementing MLOps on Snowflake*, addresses those decisions in practical terms: how work moves from Notebooks in Workspaces to modular code, repeatable execution, orchestration, CI/CD, testing, monitoring, and support.

## References

### MLOps foundations and standards

- Sculley et al., *Hidden Technical Debt in Machine Learning Systems*, 2015 — https://papers.nips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html
- Kreuzberger, Kühl and Hirschl, *Machine Learning Operations (MLOps): Overview, Definition, and Architecture*, 2023 — https://doi.org/10.1109/ACCESS.2023.3262138
- Paleyes, Urma and Lawrence, *Challenges in Deploying Machine Learning*, 2022 — https://doi.org/10.1145/3533378
- Zarour, Alzabut and Al-Sarayreh, *MLOps Best Practices, Challenges and Maturity Models*, 2025 — https://doi.org/10.1016/j.infsof.2025.107733
- ISO/IEC 5338:2023 — https://www.iso.org/standard/81118.html
- NIST AI RMF 1.0 — https://doi.org/10.6028/NIST.AI.100-1
- ISO/IEC 42001:2023 — https://www.iso.org/standard/42001

### Snowflake capability references

- Snowflake ML overview — https://docs.snowflake.com/en/developer-guide/snowflake-ml/overview
- Feature Store — https://docs.snowflake.com/en/developer-guide/snowflake-ml/feature-store/overview
- Datasets — https://docs.snowflake.com/en/developer-guide/snowflake-ml/dataset
- Experiments — https://docs.snowflake.com/en/developer-guide/snowflake-ml/experiments
- Model Registry — https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview
- Inference overview — https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/inference-overview
- ML Observability — https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/model-observability
- ML Lineage — https://docs.snowflake.com/en/developer-guide/snowflake-ml/ml-lineage
- Task Graphs — https://docs.snowflake.com/en/developer-guide/snowflake-python-api/snowflake-python-managing-tasks

Product capabilities and availability status referenced as of September 2026.