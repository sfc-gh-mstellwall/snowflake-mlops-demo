-- Reserved delayed-outcome evidence. Do not regenerate bootstrap to advance time.
-- Execute only after authorised Demo 4 rehearsal planning.

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE {{WAREHOUSE}};
USE DATABASE {{DATABASE}};
USE SCHEMA {{CONTROL_SCHEMA}};

CREATE TABLE IF NOT EXISTS PREDICTION_RECORD (
  PREDICTION_ID VARCHAR COMMENT 'Stable prediction identifier',
  ACCOUNT_ID VARCHAR COMMENT 'Scored facility identifier',
  OBSERVATION_DATE DATE COMMENT 'Prediction observation date',
  SCORED_AT TIMESTAMP_NTZ COMMENT 'Actual scoring time',
  MODEL_DATABASE VARCHAR COMMENT 'Database of the serving model',
  MODEL_SCHEMA VARCHAR COMMENT 'Schema of the serving model',
  MODEL_NAME VARCHAR COMMENT 'Serving model collection name',
  MODEL_VERSION VARCHAR COMMENT 'Exact served model version',
  RELEASE_ID VARCHAR COMMENT 'Source release used to score',
  SCORE NUMBER(10,6) COMMENT 'Predicted default probability',
  PREDICTION_CLASS NUMBER(1,0) COMMENT 'Predicted class when materialised',
  BATCH_ID VARCHAR COMMENT 'Scoring batch identifier',
  FEATURE_CONTRACT VARCHAR COMMENT 'Pinned feature and inference contract'
) COMMENT = 'Durable warehouse-batch prediction evidence';

CREATE TABLE IF NOT EXISTS OPERATIONAL_ACTION (
  ACTION_ID VARCHAR COMMENT 'Reviewed operating-action identifier',
  PREDICTION_ID VARCHAR COMMENT 'Prediction that prompted review when applicable',
  MODEL_VERSION VARCHAR COMMENT 'Model version under review',
  ACTION VARCHAR COMMENT 'investigate, retain, repair, train_candidate, recover, or retire',
  RATIONALE VARCHAR COMMENT 'Recorded reason for the action',
  LAUNCHES_TRAINING BOOLEAN COMMENT 'False unless a separate authorised training start exists',
  CHANGES_INCUMBENT BOOLEAN COMMENT 'False unless a separate serving change exists',
  RECORDED_BY VARCHAR COMMENT 'Accountable reviewer',
  RECORDED_AT TIMESTAMP_NTZ COMMENT 'Action timestamp'
) COMMENT = 'Reviewed monitoring actions; recommendations do not mutate serving';

GRANT SELECT, INSERT ON TABLE {{DATABASE}}.{{CONTROL_SCHEMA}}.PREDICTION_RECORD
  TO ROLE {{SERVICE_ROLE}};
GRANT SELECT ON TABLE {{DATABASE}}.{{CONTROL_SCHEMA}}.PREDICTION_RECORD
  TO ROLE {{ENGINEER_ROLE}};
GRANT SELECT ON TABLE {{DATABASE}}.{{CONTROL_SCHEMA}}.PREDICTION_RECORD
  TO ROLE {{PROD_OWNER_ROLE}};
REVOKE UPDATE ON TABLE {{DATABASE}}.{{CONTROL_SCHEMA}}.PREDICTION_RECORD
  FROM ROLE {{SERVICE_ROLE}};

GRANT SELECT, INSERT ON TABLE {{DATABASE}}.{{CONTROL_SCHEMA}}.OPERATIONAL_ACTION
  TO ROLE {{PROD_OWNER_ROLE}};
GRANT SELECT ON TABLE {{DATABASE}}.{{CONTROL_SCHEMA}}.OPERATIONAL_ACTION
  TO ROLE {{ENGINEER_ROLE}};
REVOKE INSERT, UPDATE ON TABLE {{DATABASE}}.{{CONTROL_SCHEMA}}.OPERATIONAL_ACTION
  FROM ROLE {{SERVICE_ROLE}};

SELECT 'MONITORING_CONTRACTS_READY' AS STATUS,
  'Do not regenerate bootstrap to advance time' AS REPLAY_RULE;
