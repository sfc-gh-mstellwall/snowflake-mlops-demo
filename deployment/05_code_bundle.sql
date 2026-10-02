-- On-demand Code Bundle deploy and inspect helpers.
-- Execute these statements from a Workspace SQL file, never a notebook cell.
-- Render with scripts/render_sql.py and review before authorised execution.

USE ROLE {{ENGINEER_ROLE}};
USE WAREHOUSE {{WAREHOUSE}};
USE DATABASE {{DATABASE}};
USE SCHEMA {{DEV_SCHEMA}};

-- Upload an allowlisted payload from scripts/build_release.py first.
-- Do not create a production release from Workspace versions/live.
CREATE CODE BUNDLE IF NOT EXISTS {{DATABASE}}.{{DEV_SCHEMA}}.CRISK_DEMO_TRAIN_R_PENDING
  FROM '@{{DATABASE}}.{{CONTROL_SCHEMA}}.{{RELEASE_STAGE}}/pending-review'
  COMMENT = 'Replace R_PENDING with the reviewed release identifier before execution';

SHOW CODE BUNDLES;

-- Authorised execution only. Arguments remain strings.
-- EXECUTE CODE BUNDLE {{DATABASE}}.{{DEV_SCHEMA}}.CRISK_DEMO_TRAIN_R_PENDING
--   ENTRYPOINT = 'jobs/train.py'
--   ARGUMENTS = ('--environment', 'DEV', '--release-id', 'R_PENDING', '--dataset-version', 'PASTE_DATASET_VERSION');

SELECT *
FROM TABLE(SNOWFLAKE.INFORMATION_SCHEMA.CODE_BUNDLE_HISTORY(
  DATABASE => '{{DATABASE}}',
  SCHEMA => '{{DEV_SCHEMA}}',
  RESULT_LIMIT => 20
));

SELECT 'CODE_BUNDLE_SCRIPTS_RENDERED' AS STATUS,
  'Never execute this from a notebook cell' AS INVOCATION_RULE;
