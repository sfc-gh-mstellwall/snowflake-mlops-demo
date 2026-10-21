from __future__ import annotations

from typing import Any

from snowflake.ml.dataset import load_dataset
from snowflake.ml.feature_store import CreationMode, Entity, Feature, FeatureStore, FeatureView
from snowflake.snowpark import Session, Window
from snowflake.snowpark import functions as F


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
    entity_names = {
        row["NAME"] for row in fs.list_entities().select("NAME").collect()
    }
    if "CREDIT_ACCOUNT" not in entity_names:
        fs.register_entity(
            Entity(
                name="CREDIT_ACCOUNT",
                join_keys=["ACCOUNT_ID"],
                desc="Credit account or facility entity key for default prediction",
            )
        )
    credit_account = fs.get_entity("CREDIT_ACCOUNT")

    existing_fvs = {
        (row["NAME"], str(row["VERSION"]))
        for row in fs.list_feature_views().select("NAME", "VERSION").collect()
    }
    required_names = [
        "ACCOUNT_AGGREGATION_FV",
        "ACCOUNT_PAYMENT_FV",
        "ACCOUNT_CONTACT_FV",
        "ACCOUNT_PROFILE_FV",
        "ACCOUNT_BALANCE_FV",
        "ACCOUNT_DELINQUENCY_FV",
    ]
    if all((name, version) in existing_fvs for name in required_names):
        return fs, [fs.get_feature_view(name, version) for name in required_names]

    dim_account = session.table(f"{database_name}.{raw_schema}.DIM_CREDIT_ACCOUNT")
    dim_customer = session.table(f"{database_name}.{raw_schema}.DIM_CUSTOMER")
    fin_snap = session.table(f"{database_name}.{raw_schema}.FACT_CUSTOMER_FINANCIAL_SNAPSHOT")
    acct_event = session.table(f"{database_name}.{raw_schema}.FACT_ACCOUNT_EVENT")
    daily_snap = session.table(f"{database_name}.{raw_schema}.FACT_ACCOUNT_DAILY_SNAPSHOT")
    fact_payment = session.table(f"{database_name}.{raw_schema}.FACT_PAYMENT")
    fact_contact = session.table(f"{database_name}.{raw_schema}.FACT_CUSTOMER_CONTACT")

    # 1. Tiled daily snapshot aggregations
    daily_base = daily_snap.select(
        "ACCOUNT_ID",
        F.to_timestamp_ntz("SNAPSHOT_DATE").alias("FEATURE_TS"),
        F.col("UTILISATION_RATIO").cast("FLOAT").alias("UTILISATION_RATIO"),
        F.col("BALANCE_AMOUNT").cast("FLOAT").alias("BALANCE_AMOUNT"),
        F.col("DAYS_PAST_DUE").cast("FLOAT").alias("DAYS_PAST_DUE"),
        F.iff(F.col("DAYS_PAST_DUE") >= 30, 1.0, 0.0).alias("IS_DPD_30_PLUS"),
        F.iff(F.col("DAYS_PAST_DUE") >= 60, 1.0, 0.0).alias("IS_DPD_60_PLUS"),
    )
    agg_fv_def = FeatureView(
        name="ACCOUNT_AGGREGATION_FV",
        entities=[credit_account],
        feature_df=daily_base,
        timestamp_col="FEATURE_TS",
        refresh_freq="1 day",
        feature_granularity="1 day",
        features=[
            Feature.avg("UTILISATION_RATIO", "30d").alias("AVG_UTILISATION_30D"),
            Feature.avg("UTILISATION_RATIO", "90d").alias("AVG_UTILISATION_90D"),
            Feature.avg("UTILISATION_RATIO", "180d").alias("AVG_UTILISATION_180D"),
            Feature.max("UTILISATION_RATIO", "90d").alias("MAX_UTILISATION_90D"),
            Feature.stddev("UTILISATION_RATIO", "90d").alias("STD_UTILISATION_90D"),
            Feature.avg("BALANCE_AMOUNT", "30d").alias("AVG_BALANCE_30D"),
            Feature.avg("BALANCE_AMOUNT", "90d").alias("AVG_BALANCE_90D"),
            Feature.avg("BALANCE_AMOUNT", "180d").alias("AVG_BALANCE_180D"),
            Feature.max("DAYS_PAST_DUE", "90d").alias("MAX_DAYS_PAST_DUE_90D"),
            Feature.max("DAYS_PAST_DUE", "180d").alias("MAX_DAYS_PAST_DUE_180D"),
            Feature.max("DAYS_PAST_DUE", "365d").alias("MAX_DAYS_PAST_DUE_365D"),
            Feature.sum("IS_DPD_30_PLUS", "180d").alias("DAYS_30_PLUS_180D"),
            Feature.sum("IS_DPD_60_PLUS", "365d").alias("DAYS_60_PLUS_365D"),
        ],
        desc="Tiled 30/90/180/365d balance, utilisation, and delinquency aggregations",
    )
    agg_fv = (
        fs.get_feature_view("ACCOUNT_AGGREGATION_FV", version)
        if ("ACCOUNT_AGGREGATION_FV", version) in existing_fvs
        else fs.register_feature_view(agg_fv_def, version=version)
    )

    # 2. Tiled payment aggregations
    payment_base = fact_payment.select(
        "ACCOUNT_ID",
        F.to_timestamp_ntz("PAYMENT_DATE").alias("FEATURE_TS"),
        F.col("PAYMENT_AMOUNT").cast("FLOAT").alias("PAYMENT_AMOUNT"),
        F.iff(F.col("PAYMENT_STATUS") == "MISSED", 1.0, 0.0).alias("IS_MISSED_PAYMENT"),
        F.iff(F.col("PAYMENT_STATUS") == "REVERSED", 1.0, 0.0).alias("IS_REVERSED_PAYMENT"),
        F.iff(F.col("PAYMENT_CHANNEL") == "AUTOPAY", 1.0, 0.0).alias("IS_AUTOPAY"),
    )
    payment_fv_def = FeatureView(
        name="ACCOUNT_PAYMENT_FV",
        entities=[credit_account],
        feature_df=payment_base,
        timestamp_col="FEATURE_TS",
        refresh_freq="1 day",
        feature_granularity="1 day",
        features=[
            Feature.sum("PAYMENT_AMOUNT", "30d").alias("PAYMENT_SUM_30D"),
            Feature.sum("PAYMENT_AMOUNT", "90d").alias("PAYMENT_SUM_90D"),
            Feature.sum("PAYMENT_AMOUNT", "180d").alias("PAYMENT_SUM_180D"),
            Feature.sum("IS_MISSED_PAYMENT", "90d").alias("MISSED_PAYMENT_COUNT_90D"),
            Feature.sum("IS_MISSED_PAYMENT", "180d").alias("MISSED_PAYMENT_COUNT_180D"),
            Feature.sum("IS_REVERSED_PAYMENT", "180d").alias("REVERSED_PAYMENT_COUNT_180D"),
            Feature.avg("IS_AUTOPAY", "180d").alias("AUTOPAY_SHARE_180D"),
        ],
        desc="Tiled payment sums, missed/reversed counts, and autopay share",
    )
    payment_fv = (
        fs.get_feature_view("ACCOUNT_PAYMENT_FV", version)
        if ("ACCOUNT_PAYMENT_FV", version) in existing_fvs
        else fs.register_feature_view(payment_fv_def, version=version)
    )

    # 3. Tiled contact aggregations
    contact_base = fact_contact.select(
        "ACCOUNT_ID",
        F.to_timestamp_ntz("CONTACT_TIMESTAMP").alias("FEATURE_TS"),
        F.lit(1.0).alias("IS_CONTACT"),
        F.iff(F.col("CONTACT_REASON") == "HARDSHIP", 1.0, 0.0).alias("IS_HARDSHIP_CONTACT"),
        F.iff(F.col("OUTCOME_CODE") == "PROMISE_TO_PAY", 1.0, 0.0).alias("IS_PROMISE_TO_PAY"),
        F.iff(F.col("OUTCOME_CODE") == "BROKEN_PROMISE", 1.0, 0.0).alias("IS_BROKEN_PROMISE"),
    )
    contact_fv_def = FeatureView(
        name="ACCOUNT_CONTACT_FV",
        entities=[credit_account],
        feature_df=contact_base,
        timestamp_col="FEATURE_TS",
        refresh_freq="1 day",
        feature_granularity="1 day",
        features=[
            Feature.sum("IS_CONTACT", "90d").alias("CONTACT_COUNT_90D"),
            Feature.sum("IS_HARDSHIP_CONTACT", "180d").alias("HARDSHIP_CONTACT_COUNT_180D"),
            Feature.sum("IS_PROMISE_TO_PAY", "180d").alias("PROMISE_TO_PAY_COUNT_180D"),
            Feature.sum("IS_BROKEN_PROMISE", "180d").alias("BROKEN_PROMISE_COUNT_180D"),
        ],
        desc="Tiled customer contact, hardship, and promise-to-pay counts",
    )
    contact_fv = (
        fs.get_feature_view("ACCOUNT_CONTACT_FV", version)
        if ("ACCOUNT_CONTACT_FV", version) in existing_fvs
        else fs.register_feature_view(contact_fv_def, version=version)
    )

    # 4. Profile, Balance, and Delinquency Feature Views
    acct_w = Window.partition_by("ACCOUNT_ID").order_by("SNAPSHOT_DATE")
    monthly_snaps = (
        daily_snap.with_column("LAG_UTIL_30D", F.lag("UTILISATION_RATIO", 30).over(acct_w))
        .with_column("LAG_UTIL_90D", F.lag("UTILISATION_RATIO", 90).over(acct_w))
        .with_column("LAG_BAL_90D", F.lag("BALANCE_AMOUNT", 90).over(acct_w))
        .with_column("LAG_DPD_1D", F.lag("DAYS_PAST_DUE", 1).over(acct_w))
        .with_column(
            "DELINQUENCY_ENTRY",
            F.iff(
                (F.col("DAYS_PAST_DUE") > 0) & (F.coalesce(F.col("LAG_DPD_1D"), F.lit(0)) == 0),
                1.0,
                0.0,
            ),
        )
        .with_column(
            "DELINQUENCY_EPISODE_COUNT_180D",
            F.sum("DELINQUENCY_ENTRY").over(acct_w.rows_between(-179, Window.CURRENT_ROW)),
        )
        .with_column(
            "AVG_MIN_DUE_30D",
            F.avg("MINIMUM_DUE_AMOUNT").over(acct_w.rows_between(-29, Window.CURRENT_ROW)),
        )
        .with_column(
            "AVG_MIN_DUE_90D",
            F.avg("MINIMUM_DUE_AMOUNT").over(acct_w.rows_between(-89, Window.CURRENT_ROW)),
        )
        .with_column(
            "AVG_BAL_30D_LOCAL",
            F.avg("BALANCE_AMOUNT").over(acct_w.rows_between(-29, Window.CURRENT_ROW)),
        )
        .filter(F.col("SNAPSHOT_DATE") == F.last_day(F.col("SNAPSHOT_DATE")))
    )

    limit_events = acct_event.filter(
        F.col("EVENT_TYPE").isin(["LIMIT_INCREASE", "LIMIT_DECREASE"])
    ).select(
        F.col("ACCOUNT_ID").alias("EV_ACCOUNT_ID"),
        F.col("EVENT_DATE"),
        F.col("OLD_CREDIT_LIMIT"),
        F.col("NEW_CREDIT_LIMIT"),
    )
    joined_profile = (
        monthly_snaps.join(dim_account, on="ACCOUNT_ID")
        .join(dim_customer, on="CUSTOMER_ID")
        .join(
            fin_snap.select(
                F.col("CUSTOMER_ID").alias("FS_CUST_ID"),
                F.col("EFFECTIVE_DATE"),
                F.col("ANNUAL_INCOME_ESTIMATE"),
            ),
            (F.col("CUSTOMER_ID") == F.col("FS_CUST_ID"))
            & (F.col("EFFECTIVE_DATE") <= F.col("SNAPSHOT_DATE")),
            join_type="left",
        )
        .with_column(
            "RN_FIN",
            F.row_number().over(
                Window.partition_by("ACCOUNT_ID", "SNAPSHOT_DATE").order_by(
                    F.col("EFFECTIVE_DATE").desc_nulls_last()
                )
            ),
        )
        .filter(F.col("RN_FIN") == 1)
        .join(
            limit_events,
            (F.col("ACCOUNT_ID") == F.col("EV_ACCOUNT_ID"))
            & (F.col("EVENT_DATE") <= F.col("SNAPSHOT_DATE")),
            join_type="left",
        )
        .with_column(
            "RN_LIM",
            F.row_number().over(
                Window.partition_by("ACCOUNT_ID", "SNAPSHOT_DATE").order_by(
                    F.col("EVENT_DATE").desc_nulls_last()
                )
            ),
        )
        .filter(F.col("RN_LIM") == 1)
    )

    profile_df = joined_profile.select(
        "ACCOUNT_ID",
        F.to_timestamp_ntz("SNAPSHOT_DATE").alias("FEATURE_TS"),
        "PRODUCT_CODE",
        "ORIGINATION_CHANNEL",
        F.datediff("month", F.col("OPEN_DATE"), F.col("SNAPSHOT_DATE"))
        .cast("FLOAT")
        .alias("ACCOUNT_AGE_MONTHS"),
        F.datediff("month", F.col("CUSTOMER_SINCE_DATE"), F.col("SNAPSHOT_DATE"))
        .cast("FLOAT")
        .alias("CUSTOMER_TENURE_MONTHS"),
        F.col("CREDIT_LIMIT").cast("FLOAT").alias("CURRENT_CREDIT_LIMIT"),
        F.coalesce(F.col("ANNUAL_INCOME_ESTIMATE"), F.col("INITIAL_ANNUAL_INCOME"))
        .cast("FLOAT")
        .alias("CURRENT_INCOME_ESTIMATE"),
        F.call_builtin(
            "DIV0",
            F.col("CREDIT_LIMIT"),
            F.coalesce(F.col("ANNUAL_INCOME_ESTIMATE"), F.col("INITIAL_ANNUAL_INCOME")),
        )
        .cast("FLOAT")
        .alias("LIMIT_TO_INCOME_RATIO"),
        F.coalesce(
            F.datediff("month", F.col("EVENT_DATE"), F.col("SNAPSHOT_DATE")),
            F.datediff("month", F.col("OPEN_DATE"), F.col("SNAPSHOT_DATE")),
        )
        .cast("FLOAT")
        .alias("MONTHS_SINCE_LIMIT_CHANGE"),
        F.iff(
            F.col("EVENT_DATE").is_not_null()
            & (F.datediff("day", F.col("EVENT_DATE"), F.col("SNAPSHOT_DATE")) <= 365),
            F.call_builtin(
                "DIV0",
                F.col("NEW_CREDIT_LIMIT") - F.col("OLD_CREDIT_LIMIT"),
                F.col("OLD_CREDIT_LIMIT"),
            ),
            F.lit(0.0),
        )
        .cast("FLOAT")
        .alias("LIMIT_CHANGE_PERCENT_12M"),
    )

    spine_for_pay = monthly_snaps.select(
        "ACCOUNT_ID",
        F.to_timestamp_ntz("SNAPSHOT_DATE").alias("FEATURE_TS"),
        "BALANCE_AMOUNT",
        "CREDIT_LIMIT",
        "UTILISATION_RATIO",
        "LAG_UTIL_30D",
        "LAG_UTIL_90D",
        "LAG_BAL_90D",
        "AVG_MIN_DUE_30D",
        "AVG_MIN_DUE_90D",
        "AVG_BAL_30D_LOCAL",
    )
    with_pay = fs.retrieve_feature_values(
        spine_df=spine_for_pay,
        features=[payment_fv],
        spine_timestamp_col="FEATURE_TS",
        join_method="cte",
    )
    balance_df = with_pay.select(
        "ACCOUNT_ID",
        "FEATURE_TS",
        F.col("BALANCE_AMOUNT").cast("FLOAT").alias("CURRENT_BALANCE"),
        (F.col("CREDIT_LIMIT") - F.col("BALANCE_AMOUNT")).cast("FLOAT").alias("AVAILABLE_CREDIT"),
        F.col("UTILISATION_RATIO").cast("FLOAT").alias("CURRENT_UTILISATION"),
        (F.col("UTILISATION_RATIO") - F.coalesce(F.col("LAG_UTIL_30D"), F.col("UTILISATION_RATIO")))
        .cast("FLOAT")
        .alias("UTILISATION_CHANGE_30D"),
        (F.col("UTILISATION_RATIO") - F.coalesce(F.col("LAG_UTIL_90D"), F.col("UTILISATION_RATIO")))
        .cast("FLOAT")
        .alias("UTILISATION_CHANGE_90D"),
        F.call_builtin(
            "DIV0",
            F.col("BALANCE_AMOUNT") - F.coalesce(F.col("LAG_BAL_90D"), F.col("BALANCE_AMOUNT")),
            F.greatest(F.coalesce(F.col("LAG_BAL_90D"), F.lit(1.0)), F.lit(1.0)),
        )
        .cast("FLOAT")
        .alias("BALANCE_CHANGE_PCT_90D"),
        F.iff(F.col("UTILISATION_RATIO") >= 0.95, 1.0, 0.0).alias("OVER_95_UTILISATION_FLAG"),
        F.call_builtin("DIV0", F.coalesce(F.col("PAYMENT_SUM_30D"), F.lit(0.0)), F.col("AVG_MIN_DUE_30D"))
        .cast("FLOAT")
        .alias("PAYMENT_TO_MIN_DUE_RATIO_30D"),
        F.call_builtin("DIV0", F.coalesce(F.col("PAYMENT_SUM_90D"), F.lit(0.0)), F.col("AVG_MIN_DUE_90D") * 3.0)
        .cast("FLOAT")
        .alias("PAYMENT_TO_MIN_DUE_RATIO_90D"),
        F.call_builtin("DIV0", F.coalesce(F.col("PAYMENT_SUM_30D"), F.lit(0.0)), F.col("AVG_BAL_30D_LOCAL"))
        .cast("FLOAT")
        .alias("PAYMENT_TO_BALANCE_RATIO_30D"),
        (
            F.coalesce(F.col("PAYMENT_SUM_90D"), F.lit(0.0))
            - (F.coalesce(F.col("PAYMENT_SUM_180D"), F.lit(0.0)) - F.coalesce(F.col("PAYMENT_SUM_90D"), F.lit(0.0)))
        )
        .cast("FLOAT")
        .alias("PAYMENT_AMOUNT_TREND_90D_VS_PRIOR_90D"),
    )

    delinquency_df = monthly_snaps.select(
        "ACCOUNT_ID",
        F.to_timestamp_ntz("SNAPSHOT_DATE").alias("FEATURE_TS"),
        F.col("DAYS_PAST_DUE").cast("FLOAT").alias("CURRENT_DAYS_PAST_DUE"),
        F.col("DELINQUENCY_EPISODE_COUNT_180D").cast("FLOAT").alias("DELINQUENCY_EPISODE_COUNT_180D"),
    )

    profile_fv = (
        fs.get_feature_view("ACCOUNT_PROFILE_FV", version)
        if ("ACCOUNT_PROFILE_FV", version) in existing_fvs
        else fs.register_feature_view(
            FeatureView(
                name="ACCOUNT_PROFILE_FV",
                entities=[credit_account],
                feature_df=profile_df,
                timestamp_col="FEATURE_TS",
                desc="Point-in-time account, tenure, credit limit, and income profile features",
            ),
            version=version,
        )
    )
    balance_fv = (
        fs.get_feature_view("ACCOUNT_BALANCE_FV", version)
        if ("ACCOUNT_BALANCE_FV", version) in existing_fvs
        else fs.register_feature_view(
            FeatureView(
                name="ACCOUNT_BALANCE_FV",
                entities=[credit_account],
                feature_df=balance_df,
                timestamp_col="FEATURE_TS",
                desc="Point-in-time balance, utilisation deltas, and payment ratios",
            ),
            version=version,
        )
    )
    delinquency_fv = (
        fs.get_feature_view("ACCOUNT_DELINQUENCY_FV", version)
        if ("ACCOUNT_DELINQUENCY_FV", version) in existing_fvs
        else fs.register_feature_view(
            FeatureView(
                name="ACCOUNT_DELINQUENCY_FV",
                entities=[credit_account],
                feature_df=delinquency_df,
                timestamp_col="FEATURE_TS",
                desc="Point-in-time current days past due and 180d delinquency episode counts",
            ),
            version=version,
        )
    )

    return fs, [agg_fv, payment_fv, contact_fv, profile_fv, balance_fv, delinquency_fv]


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
    refit_cutoff: str = "2025-10-01",
    holdout_cutoff: str = "2026-01-01",
) -> dict[str, Any]:
    """Ensure immutable CREDIT_REFIT, CREDIT_HELD_OUT, and CREDIT_VALIDATION datasets exist."""
    fs, feature_views = ensure_environment_feature_store(
        session,
        database_name=database_name,
        raw_schema=raw_schema,
        feature_store_schema=feature_store_schema,
        warehouse_name=warehouse_name,
    )
    ground_truth = (
        session.table(f"{database_name}.{raw_schema}.AVAILABLE_GROUND_TRUTH")
        .with_column("OBSERVATION_TS", F.to_timestamp_ntz("OBSERVATION_DATE"))
        .select(
            "OBSERVATION_ID",
            "ACCOUNT_ID",
            "CUSTOMER_ID",
            "OBSERVATION_DATE",
            "OBSERVATION_TS",
            "OUTCOME_FINALITY_DATE",
            "DEFAULT_WITHIN_90D",
        )
    )

    validation_spine = ground_truth.filter(
        (F.col("OBSERVATION_DATE") >= F.to_date(F.lit(development_cutoff)))
        & (F.col("OBSERVATION_DATE") < F.to_date(F.lit(refit_cutoff)))
        & (F.col("OUTCOME_FINALITY_DATE") < F.to_date(F.lit(refit_cutoff)))
    )
    refit_spine = ground_truth.filter(
        (F.col("OBSERVATION_DATE") < F.to_date(F.lit(refit_cutoff)))
        & (F.col("OUTCOME_FINALITY_DATE") < F.to_date(F.lit(refit_cutoff)))
    )
    held_out_spine = ground_truth.filter(
        (F.col("OBSERVATION_DATE") >= F.to_date(F.lit(refit_cutoff)))
        & (F.col("OBSERVATION_DATE") < F.to_date(F.lit(holdout_cutoff)))
        & (F.col("OUTCOME_FINALITY_DATE") < F.to_date(F.lit(holdout_cutoff)))
    )

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
                join_method="cte",
                desc=f"Immutable {ds_key} dataset generated from {feature_store_schema}@V01",
            )
    return datasets
