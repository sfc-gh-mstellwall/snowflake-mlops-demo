from __future__ import annotations

from typing import Any

from snowflake.ml.dataset import load_dataset
from snowflake.ml.feature_store import CreationMode, Entity, Feature, FeatureStore, FeatureView
from snowflake.snowpark import Session, Window
from snowflake.snowpark import functions as F

# Define the SQL DIV0NULL function once via F.function() so repeated zero-safe
# ratio expressions reuse a single function handle across Feature Views.
div0null = F.function("DIV0NULL")


def ensure_environment_feature_store(
    session: Session,
    *,
    database_name: str,
    raw_schema: str,
    feature_store_schema: str,
    warehouse_name: str,
    version: str = "V01",
) -> tuple[FeatureStore, list[FeatureView]]:
    """Ensure the target environment's Feature Store has all 6 pinned V01 Feature Views."""
    fs = FeatureStore(
        session=session,
        database=database_name,
        name=feature_store_schema,
        default_warehouse=warehouse_name,
        creation_mode=CreationMode.CREATE_IF_NOT_EXIST,
    )
    if fs.list_entities().filter(F.col("NAME") == "CREDIT_ACCOUNT").count() == 0:
        fs.register_entity(
            Entity(
                name="CREDIT_ACCOUNT",
                join_keys=["ACCOUNT_ID"],
                desc="Credit account or facility entity key for default prediction",
            )
        )
    credit_account = fs.get_entity("CREDIT_ACCOUNT")

    required_names = [
        "ACCOUNT_AGGREGATION_FV",
        "ACCOUNT_PAYMENT_FV",
        "ACCOUNT_CONTACT_FV",
        "ACCOUNT_PROFILE_FV",
        "ACCOUNT_BALANCE_FV",
        "ACCOUNT_DELINQUENCY_FV",
    ]
    existing_count = (
        fs.list_feature_views()
        .filter(F.col("NAME").isin(required_names) & (F.col("VERSION") == version))
        .count()
    )
    if existing_count == len(required_names):
        return fs, [fs.get_feature_view(name, version) for name in required_names]

    # Single point of definition: bind every RAW source table once as a lazy Snowpark DataFrame.
    accounts = session.table(f"{database_name}.{raw_schema}.DIM_CREDIT_ACCOUNT")
    customers = session.table(f"{database_name}.{raw_schema}.DIM_CUSTOMER")
    financials = session.table(f"{database_name}.{raw_schema}.FACT_CUSTOMER_FINANCIAL_SNAPSHOT")
    events = session.table(f"{database_name}.{raw_schema}.FACT_ACCOUNT_EVENT")
    daily = session.table(f"{database_name}.{raw_schema}.FACT_ACCOUNT_DAILY_SNAPSHOT")
    payments = session.table(f"{database_name}.{raw_schema}.FACT_PAYMENT")
    contacts = session.table(f"{database_name}.{raw_schema}.FACT_CUSTOMER_CONTACT")
    observations = session.table(f"{database_name}.{raw_schema}.ACCOUNT_OBSERVATION")

    # 1. Account profile Feature View
    limit_events = (
        events.filter(F.col("EVENT_TYPE") == "CREDIT_LIMIT_CHANGE")
        .select(
            "ACCOUNT_ID",
            F.to_date("EVENT_TIMESTAMP").alias("EVENT_DATE"),
            F.col("OLD_VALUE").cast("double").alias("OLD_LIMIT"),
            F.col("NEW_VALUE").cast("double").alias("NEW_LIMIT"),
        )
    )
    monthly_daily = daily.filter(F.dayofmonth(F.dateadd("day", F.lit(1), "SNAPSHOT_DATE")) == 1)
    profile_candidates = (
        monthly_daily.join(accounts, "ACCOUNT_ID")
        .join(customers, "CUSTOMER_ID")
        .join(
            financials,
            (customers["CUSTOMER_ID"] == financials["CUSTOMER_ID"])
            & (financials["SNAPSHOT_DATE"] == F.trunc(monthly_daily["SNAPSHOT_DATE"], F.lit("MONTH"))),
        )
        .join(
            limit_events,
            (monthly_daily["ACCOUNT_ID"] == limit_events["ACCOUNT_ID"])
            & (limit_events["EVENT_DATE"] <= monthly_daily["SNAPSHOT_DATE"]),
            how="left",
        )
        .select(
            monthly_daily["ACCOUNT_ID"].alias("ACCOUNT_ID"),
            monthly_daily["SNAPSHOT_DATE"].alias("MNTH_DAY_SNAPSHOT_DATE"),
            financials["SNAPSHOT_DATE"].alias("FINANCIAL_SNAPSHOT_DATE"),
            "EVENT_DATE",
            "PRODUCT_CODE",
            "ORIGINATION_CHANNEL",
            "OPEN_DATE",
            "CUSTOMER_SINCE_DATE",
            monthly_daily["CREDIT_LIMIT"].alias("CREDIT_LIMIT"),
            "MONTHLY_INCOME_ESTIMATE",
            "NEW_LIMIT",
            "OLD_LIMIT",
        )
    )
    latest_available = Window.partition_by("ACCOUNT_ID", "MNTH_DAY_SNAPSHOT_DATE").order_by(
        F.col("FINANCIAL_SNAPSHOT_DATE").desc(), F.col("EVENT_DATE").desc_nulls_last()
    )
    profile_df = (
        profile_candidates.with_column("AVAILABILITY_ORDER", F.row_number().over(latest_available))
        .filter(F.col("AVAILABILITY_ORDER") == 1)
        .select(
            "ACCOUNT_ID",
            F.dateadd("day", F.lit(1), F.col("MNTH_DAY_SNAPSHOT_DATE"))
            .cast("timestamp_ntz")
            .alias("PROFILE_TS"),
            "PRODUCT_CODE",
            "ORIGINATION_CHANNEL",
            F.datediff("month", F.col("OPEN_DATE"), F.col("MNTH_DAY_SNAPSHOT_DATE")).alias(
                "ACCOUNT_AGE_MONTHS"
            ),
            F.datediff("month", F.col("CUSTOMER_SINCE_DATE"), F.col("MNTH_DAY_SNAPSHOT_DATE")).alias(
                "CUSTOMER_TENURE_MONTHS"
            ),
            F.col("CREDIT_LIMIT").alias("CURRENT_CREDIT_LIMIT"),
            F.col("MONTHLY_INCOME_ESTIMATE").alias("CURRENT_INCOME_ESTIMATE"),
            div0null(F.col("CREDIT_LIMIT"), F.col("MONTHLY_INCOME_ESTIMATE")).alias(
                "LIMIT_TO_INCOME_RATIO"
            ),
            F.datediff("month", F.col("EVENT_DATE"), F.col("MNTH_DAY_SNAPSHOT_DATE")).alias(
                "MONTHS_SINCE_LIMIT_CHANGE"
            ),
            F.iff(
                F.col("EVENT_DATE")
                >= F.dateadd("month", F.lit(-12), F.col("MNTH_DAY_SNAPSHOT_DATE")),
                div0null(F.col("NEW_LIMIT") - F.col("OLD_LIMIT"), F.col("OLD_LIMIT")),
                F.lit(0.0),
            ).alias("LIMIT_CHANGE_PERCENT_12M"),
        )
    )

    # 2. Servicing window, balance, delinquency, and tiled aggregation Feature Views
    account_order = Window.partition_by("ACCOUNT_ID").order_by("SNAPSHOT_DATE")
    servicing = (
        daily.with_column(
            "UTILISATION", div0null(F.col("OUTSTANDING_BALANCE"), F.col("CREDIT_LIMIT"))
        )
        .with_column(
            "DELINQUENCY_START",
            F.iff(
                (F.col("DAYS_PAST_DUE") > 0)
                & (F.coalesce(F.lag("DAYS_PAST_DUE").over(account_order), F.lit(0)) == 0),
                1.0,
                0.0,
            ),
        )
        .with_column(
            "LATEST_DELINQUENT_DATE",
            F.max(F.iff(F.col("DAYS_PAST_DUE") > 0, F.col("SNAPSHOT_DATE"), F.lit(None))).over(
                account_order.rows_between(Window.UNBOUNDED_PRECEDING, Window.CURRENT_ROW)
            ),
        )
    )

    balance_base_df = (
        servicing.select(
            "ACCOUNT_ID",
            F.dateadd("day", F.lit(1), F.col("SNAPSHOT_DATE"))
            .cast("timestamp_ntz")
            .alias("BALANCE_TS"),
            F.col("OUTSTANDING_BALANCE").alias("CURRENT_BALANCE"),
            F.col("UTILISATION").alias("CURRENT_UTILISATION"),
            (
                F.col("OUTSTANDING_BALANCE") - F.lag("OUTSTANDING_BALANCE", 30).over(account_order)
            ).alias("BALANCE_CHANGE_30D"),
            (
                F.col("OUTSTANDING_BALANCE") - F.lag("OUTSTANDING_BALANCE", 90).over(account_order)
            ).alias("BALANCE_CHANGE_90D"),
            div0null(F.col("AVAILABLE_CREDIT"), F.col("CREDIT_LIMIT")).alias(
                "AVAILABLE_CREDIT_RATIO"
            ),
        )
        .filter(F.dayofmonth("BALANCE_TS") == 1)
    )

    delinquency_df = (
        servicing.select(
            "ACCOUNT_ID",
            F.dateadd("day", F.lit(1), F.col("SNAPSHOT_DATE"))
            .cast("timestamp_ntz")
            .alias("DELINQUENCY_TS"),
            F.col("DAYS_PAST_DUE").alias("CURRENT_DAYS_PAST_DUE"),
            F.ceil(F.col("DAYS_PAST_DUE") / F.lit(30)).alias("CONSECUTIVE_DELINQUENT_MONTHS"),
            F.datediff(
                "day", F.col("LATEST_DELINQUENT_DATE"), F.col("SNAPSHOT_DATE")
            ).alias("DAYS_SINCE_LAST_DELINQUENCY"),
        )
        .filter(F.dayofmonth("DELINQUENCY_TS") == 1)
    )

    aggregation_source = servicing.select(
        "ACCOUNT_ID",
        F.dateadd("day", F.lit(1), F.col("SNAPSHOT_DATE"))
        .cast("timestamp_ntz")
        .alias("AGGREGATION_TS"),
        F.col("UTILISATION").alias("DAILY_UTILISATION"),
        F.col("DAYS_PAST_DUE").cast("double").alias("DAILY_DAYS_PAST_DUE"),
        F.iff(
            F.col("OUTSTANDING_BALANCE") > F.col("CREDIT_LIMIT"), F.lit(1.0), F.lit(0.0)
        ).alias("IS_OVER_LIMIT"),
        F.iff(F.col("DAYS_PAST_DUE") > 0, F.lit(1.0), F.lit(0.0)).alias("IS_DELINQUENT"),
        F.col("DELINQUENCY_START").alias("DELINQUENCY_START"),
    )
    aggregation_view = FeatureView(
        name="ACCOUNT_AGGREGATION_FV",
        entities=[credit_account],
        feature_df=aggregation_source,
        feature_granularity="1 day",
        features=[
            Feature.avg("DAILY_UTILISATION", "30d").alias("AVG_UTILISATION_30D"),
            Feature.avg("DAILY_UTILISATION", "90d").alias("AVG_UTILISATION_90D"),
            Feature.max("DAILY_UTILISATION", "90d").alias("MAX_UTILISATION_90D"),
            Feature.avg("DAILY_UTILISATION", "365d").alias("AVG_UTILISATION_365D"),
            Feature.max("DAILY_UTILISATION", "365d").alias("MAX_UTILISATION_365D"),
            Feature.stddev("DAILY_UTILISATION", "90d").alias("UTILISATION_STDDEV_90D"),
            Feature.max("DAILY_DAYS_PAST_DUE", "90d").alias("MAX_DAYS_PAST_DUE_3M"),
            Feature.max("DAILY_DAYS_PAST_DUE", "180d").alias("MAX_DAYS_PAST_DUE_6M"),
            Feature.max("DAILY_DAYS_PAST_DUE", "365d").alias("MAX_DAYS_PAST_DUE_365D"),
            Feature.sum("IS_OVER_LIMIT", "30d").alias("DAYS_OVER_LIMIT_30D"),
            Feature.sum("IS_DELINQUENT", "90d").alias("DELINQUENT_DAYS_90D"),
            Feature.sum("DELINQUENCY_START", "180d").alias("DELINQUENCY_EPISODES_6M"),
        ],
        timestamp_col="AGGREGATION_TS",
        refresh_freq="1 day",
        desc="Tiled daily account behaviour aggregated over 30-, 90-, 180-, and 365-day windows.",
    )

    # 3. Payment and contact Feature Views + payment-derived balance features
    observation_dates = (
        observations.select("ACCOUNT_ID", F.col("OBSERVATION_DATE").alias("FEATURE_DATE"))
        .distinct()
    )
    prior_servicing = daily.select(
        "ACCOUNT_ID",
        F.dateadd("day", F.lit(1), F.col("SNAPSHOT_DATE")).alias("FEATURE_DATE"),
        F.col("OUTSTANDING_BALANCE").alias("PRIOR_BALANCE"),
        F.col("AMOUNT_DUE").alias("PRIOR_AMOUNT_DUE"),
    )
    payment_source = payments.select(
        "ACCOUNT_ID",
        F.dateadd("day", F.lit(1), F.col("PAYMENT_DATE"))
        .cast("timestamp_ntz")
        .alias("PAYMENT_TS"),
        "PAYMENT_ID",
        F.col("PAYMENT_AMOUNT").cast("double").alias("PAYMENT_AMOUNT"),
        F.iff(F.col("PAYMENT_STATUS") == "MISSED", F.lit(1.0), F.lit(0.0)).alias("IS_MISSED"),
    )
    payment_view = FeatureView(
        name="ACCOUNT_PAYMENT_FV",
        entities=[credit_account],
        feature_df=payment_source,
        feature_granularity="1 day",
        features=[
            Feature.sum("PAYMENT_AMOUNT", "30d").alias("PAYMENT_SUM_30D"),
            Feature.sum("PAYMENT_AMOUNT", "90d").alias("PAYMENT_SUM_90D"),
            Feature.count("PAYMENT_ID", "90d").alias("PAYMENT_COUNT_90D"),
            Feature.sum("IS_MISSED", "90d").alias("MISSED_PAYMENT_COUNT_3M"),
            Feature.sum("IS_MISSED", "180d").alias("MISSED_PAYMENT_COUNT_6M"),
        ],
        timestamp_col="PAYMENT_TS",
        refresh_freq="1 day",
        desc="Tiled payment behaviour from posted and missed payment events.",
    )

    contact_source = contacts.select(
        "ACCOUNT_ID",
        F.dateadd("day", F.lit(1), F.to_date(F.col("CONTACT_TIMESTAMP")))
        .cast("timestamp_ntz")
        .alias("CONTACT_TS"),
        "CONTACT_ID",
        F.iff(F.col("CONTACT_OUTCOME") == "BROKEN_PROMISE", F.lit(1.0), F.lit(0.0)).alias(
            "IS_BROKEN_PROMISE"
        ),
    )
    contact_view = FeatureView(
        name="ACCOUNT_CONTACT_FV",
        entities=[credit_account],
        feature_df=contact_source,
        feature_granularity="1 day",
        features=[
            Feature.count("CONTACT_ID", "30d").alias("CONTACT_COUNT_30D"),
            Feature.count("CONTACT_ID", "90d").alias("CONTACT_COUNT_90D"),
            Feature.sum("IS_BROKEN_PROMISE", "90d").alias("BROKEN_PROMISE_COUNT_90D"),
        ],
        timestamp_col="CONTACT_TS",
        refresh_freq="1 day",
        desc="Tiled servicing contact behaviour over 30- and 90-day windows.",
    )

    payment_events = observation_dates.join(
        payments,
        (observation_dates["ACCOUNT_ID"] == payments["ACCOUNT_ID"])
        & (payments["PAYMENT_DATE"] < observation_dates["FEATURE_DATE"])
        & (
            payments["PAYMENT_DATE"]
            > F.dateadd("day", F.lit(-180), observation_dates["FEATURE_DATE"])
        ),
        how="left",
    )
    payment_derived = (
        payment_events.group_by(
            observation_dates["ACCOUNT_ID"],
            observation_dates["FEATURE_DATE"],
        )
        .agg(
            F.sum(
                F.iff(
                    F.datediff("day", F.col("PAYMENT_DATE"), F.col("FEATURE_DATE")) < 30,
                    F.col("PAYMENT_AMOUNT"),
                    0,
                )
            ).alias("_PAYMENT_SUM_30D"),
            F.datediff(
                "day",
                F.max(F.iff(F.col("PAYMENT_AMOUNT") > 0, F.col("PAYMENT_DATE"), F.lit(None))),
                F.col("FEATURE_DATE"),
            ).alias("DAYS_SINCE_LAST_PAYMENT"),
            F.avg(
                F.iff(
                    F.datediff("day", F.col("PAYMENT_DATE"), F.col("FEATURE_DATE")) < 30,
                    F.col("PAYMENT_AMOUNT"),
                    F.lit(None),
                )
            ).alias("AVG_PAYMENT_RECENT_30D"),
            F.avg(
                F.iff(
                    (F.datediff("day", F.col("PAYMENT_DATE"), F.col("FEATURE_DATE")) >= 60)
                    & (F.datediff("day", F.col("PAYMENT_DATE"), F.col("FEATURE_DATE")) < 90),
                    F.col("PAYMENT_AMOUNT"),
                    F.lit(None),
                )
            ).alias("AVG_PAYMENT_EARLY_30D"),
        )
        .join(prior_servicing, ["ACCOUNT_ID", "FEATURE_DATE"], how="left")
        .select(
            "ACCOUNT_ID",
            F.col("FEATURE_DATE").cast("timestamp_ntz").alias("BALANCE_TS"),
            div0null(F.col("_PAYMENT_SUM_30D"), F.col("PRIOR_BALANCE")).alias(
                "PAYMENT_TO_BALANCE_RATIO_30D"
            ),
            div0null(F.col("_PAYMENT_SUM_30D"), F.col("PRIOR_AMOUNT_DUE")).alias(
                "PAYMENT_TO_AMOUNT_DUE_RATIO_30D"
            ),
            "DAYS_SINCE_LAST_PAYMENT",
            (F.col("AVG_PAYMENT_RECENT_30D") - F.col("AVG_PAYMENT_EARLY_30D")).alias(
                "PAYMENT_AMOUNT_TREND_3M"
            ),
        )
    )
    balance_df = balance_base_df.join(payment_derived, ["ACCOUNT_ID", "BALANCE_TS"], how="left")

    profile_view = FeatureView(
        name="ACCOUNT_PROFILE_FV",
        entities=[credit_account],
        feature_df=profile_df,
        timestamp_col="PROFILE_TS",
        refresh_freq=None,
        desc="Point-in-time account and customer profile.",
    )
    balance_view = FeatureView(
        name="ACCOUNT_BALANCE_FV",
        entities=[credit_account],
        feature_df=balance_df,
        timestamp_col="BALANCE_TS",
        refresh_freq=None,
        desc="Current balance, lag deltas, recency, and derived payment ratios.",
    )
    delinquency_view = FeatureView(
        name="ACCOUNT_DELINQUENCY_FV",
        entities=[credit_account],
        feature_df=delinquency_df,
        timestamp_col="DELINQUENCY_TS",
        refresh_freq=None,
        desc="Current delinquency state and days since last delinquency.",
    )

    registered_views: list[FeatureView] = []
    for name, fv_def in [
        ("ACCOUNT_AGGREGATION_FV", aggregation_view),
        ("ACCOUNT_PAYMENT_FV", payment_view),
        ("ACCOUNT_CONTACT_FV", contact_view),
        ("ACCOUNT_PROFILE_FV", profile_view),
        ("ACCOUNT_BALANCE_FV", balance_view),
        ("ACCOUNT_DELINQUENCY_FV", delinquency_view),
    ]:
        exists = (
            fs.list_feature_views()
            .filter((F.col("NAME") == name) & (F.col("VERSION") == version))
            .count()
            > 0
        )
        if not exists:
            fs.register_feature_view(fv_def, version=version, overwrite=False)
        registered_views.append(fs.get_feature_view(name, version))

    return fs, registered_views


def ensure_environment_datasets(
    session: Session,
    *,
    database_name: str,
    raw_schema: str,
    dataset_schema: str,
    feature_store_schema: str,
    warehouse_name: str,
    dataset_version: str,
    development_cutoff: str = "2025-07-01",
    holdout_cutoff: str = "2025-10-01",
) -> dict[str, Any]:
    """Ensure immutable CREDIT_VALIDATION, CREDIT_REFIT, and CREDIT_HELD_OUT datasets exist."""
    fs, feature_views = ensure_environment_feature_store(
        session,
        database_name=database_name,
        raw_schema=raw_schema,
        feature_store_schema=feature_store_schema,
        warehouse_name=warehouse_name,
    )
    # Single point of definition for the finalized ground-truth spine view.
    labelled_spine = (
        session.table(f"{database_name}.{raw_schema}.AVAILABLE_GROUND_TRUTH")
        .select(
            "ACCOUNT_ID",
            F.col("OBSERVATION_DATE").cast("timestamp_ntz").alias("OBSERVATION_TS"),
            "OUTCOME_FINALITY_DATE",
            "DEFAULT_WITHIN_90D",
        )
    )

    validation_spine = labelled_spine.filter(
        (F.col("OBSERVATION_TS") >= F.lit(development_cutoff))
        & (F.col("OBSERVATION_TS") < F.lit(holdout_cutoff))
        & (F.col("OUTCOME_FINALITY_DATE") < F.lit(holdout_cutoff))
    )
    refit_spine = labelled_spine.filter(
        (F.col("OBSERVATION_TS") < F.lit(holdout_cutoff))
        & (F.col("OUTCOME_FINALITY_DATE") < F.lit(holdout_cutoff))
    )
    held_out_spine = labelled_spine.filter(F.col("OBSERVATION_TS") >= F.lit(holdout_cutoff))

    datasets: dict[str, Any] = {}
    for ds_key, ds_name, spine_df in [
        ("validation", f"{database_name}.{dataset_schema}.CREDIT_VALIDATION", validation_spine),
        ("refit", f"{database_name}.{dataset_schema}.CREDIT_REFIT", refit_spine),
        ("held_out", f"{database_name}.{dataset_schema}.CREDIT_HELD_OUT", held_out_spine),
    ]:
        try:
            datasets[ds_key] = load_dataset(session, ds_name, version=dataset_version)
        except Exception:
            datasets[ds_key] = fs.generate_dataset(
                name=ds_name,
                version=dataset_version,
                spine_df=spine_df,
                features=feature_views,
                spine_timestamp_col="OBSERVATION_TS",
                spine_label_cols=["DEFAULT_WITHIN_90D"],
                include_feature_view_timestamp_col=True,
                join_method="cte",
                desc=f"Immutable {ds_key} dataset generated from {feature_store_schema}@V01",
            )
    return datasets
