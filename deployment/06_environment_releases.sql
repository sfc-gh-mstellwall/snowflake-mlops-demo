-- Deploy the same reviewed payload into Pre-Prod and Prod as separate
-- environment-specific Code Bundles. Execute from a Workspace SQL file,
-- never a notebook cell. Do not resume any schedule from this script.

USE ROLE {{ENGINEER_ROLE}};
USE WAREHOUSE {{WAREHOUSE}};
USE DATABASE {{DATABASE}};

-- Pre-Prod validates the pipeline release only.
USE SCHEMA {{TEST_SCHEMA}};
CREATE CODE BUNDLE IF NOT EXISTS {{DATABASE}}.{{TEST_SCHEMA}}.CRISK_DEMO_TRAIN_R_PENDING
  FROM '@{{DATABASE}}.{{CONTROL_SCHEMA}}.{{RELEASE_STAGE}}/pending-review'
  COMMENT = 'Pre-Prod copy of the reviewed payload; cannot approve a Prod model';
SHOW CODE BUNDLES;

-- Prod uses the same source identity and its own Feature Store bindings.
USE SCHEMA {{PROD_SCHEMA}};
CREATE CODE BUNDLE IF NOT EXISTS {{DATABASE}}.{{PROD_SCHEMA}}.CRISK_DEMO_TRAIN_R_PENDING
  FROM '@{{DATABASE}}.{{CONTROL_SCHEMA}}.{{RELEASE_STAGE}}/pending-review'
  COMMENT = 'Prod copy of the reviewed payload; trains a new candidate only';
SHOW CODE BUNDLES;

-- Authorised Pre-Prod execution example. Leave commented until rehearsal.
-- EXECUTE CODE BUNDLE {{DATABASE}}.{{TEST_SCHEMA}}.CRISK_DEMO_TRAIN_R_PENDING
--   ENTRYPOINT = 'jobs/train.py'
--   ARGUMENTS = ('--environment', 'TEST', '--release-id', 'R_PENDING', '--dataset-version', 'PASTE_DATASET_VERSION');

-- Authorised Prod training example. Leave commented until a pipeline release
-- has already been approved. This does not change live serving.
-- EXECUTE CODE BUNDLE {{DATABASE}}.{{PROD_SCHEMA}}.CRISK_DEMO_TRAIN_R_PENDING
--   ENTRYPOINT = 'jobs/train.py'
--   ARGUMENTS = ('--environment', 'PROD', '--release-id', 'R_PENDING', '--dataset-version', 'PASTE_DATASET_VERSION');

SELECT 'ENVIRONMENT_RELEASES_RENDERED' AS STATUS,
  'TEST means Pre-Prod; pipeline approval is not model approval' AS TEACHING_NOTE;
