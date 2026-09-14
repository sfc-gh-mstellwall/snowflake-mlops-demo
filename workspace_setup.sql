-- One-time prerequisite for running repository Python files in a fresh account.
-- Keep these values aligned with the compute-pool defaults in project.yaml.

USE ROLE ACCOUNTADMIN;

CREATE COMPUTE POOL IF NOT EXISTS CRISK_DEMO_POOL
  MIN_NODES = 1
  MAX_NODES = 1
  INSTANCE_FAMILY = CPU_X64_S
  AUTO_SUSPEND_SECS = 300
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Disposable CPU pool for CRISK_DEMO Workspace and ML Jobs';

ALTER COMPUTE POOL CRISK_DEMO_POOL SET
  MIN_NODES = 1
  MAX_NODES = 1
  AUTO_SUSPEND_SECS = 300
  AUTO_RESUME = TRUE;