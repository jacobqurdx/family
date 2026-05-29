-- ═══════════════════════════════════════════════════════════════════════════
-- Track 2 POC — Snowflake Infrastructure Setup
-- Run this once in Snowsight (Worksheets) or SnowSQL before deploying.
-- ═══════════════════════════════════════════════════════════════════════════

USE ROLE ACCOUNTADMIN;

-- ── 1. Database & schema ─────────────────────────────────────────────────────
CREATE DATABASE IF NOT EXISTS MEDICAL_WRITING
    COMMENT = 'AI Clinical Document Intelligence — Track 2 POC';

USE DATABASE MEDICAL_WRITING;
CREATE SCHEMA IF NOT EXISTS PUBLIC;
USE SCHEMA PUBLIC;

-- ── 2. Warehouse ─────────────────────────────────────────────────────────────
CREATE WAREHOUSE IF NOT EXISTS MEDICAL_WRITING_WH
    WAREHOUSE_SIZE    = 'X-SMALL'
    AUTO_SUSPEND      = 60        -- suspend after 60 s idle (cost control)
    AUTO_RESUME       = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT           = 'Track 2 POC query warehouse';

-- ── 3. Stage (holds Streamlit app files) ─────────────────────────────────────
CREATE STAGE IF NOT EXISTS STREAMLIT_STAGE
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
    COMMENT    = 'Streamlit app files uploaded by snow CLI';

-- ── 4. Persistence tables ────────────────────────────────────────────────────
-- Ingestion sessions (one row per session, JSON blob in VARIANT column)
CREATE TABLE IF NOT EXISTS INGESTION_SESSIONS (
    SESSION_ID  VARCHAR(50)      NOT NULL PRIMARY KEY,
    DATA        VARIANT          NOT NULL,
    UPDATED_AT  TIMESTAMP_NTZ    DEFAULT CURRENT_TIMESTAMP()
);

-- Digital twins (one row per twin)
CREATE TABLE IF NOT EXISTS DIGITAL_TWINS (
    TWIN_ID     VARCHAR(100)     NOT NULL PRIMARY KEY,
    DATA        VARIANT          NOT NULL,
    UPDATED_AT  TIMESTAMP_NTZ    DEFAULT CURRENT_TIMESTAMP()
);

-- ── 5. Grant privileges to SYSADMIN (or your deployment role) ────────────────
GRANT USAGE  ON WAREHOUSE MEDICAL_WRITING_WH            TO ROLE SYSADMIN;
GRANT ALL    ON DATABASE  MEDICAL_WRITING                TO ROLE SYSADMIN;
GRANT ALL    ON SCHEMA    MEDICAL_WRITING.PUBLIC         TO ROLE SYSADMIN;
GRANT ALL    ON ALL TABLES IN SCHEMA MEDICAL_WRITING.PUBLIC TO ROLE SYSADMIN;
GRANT ALL    ON STAGE     MEDICAL_WRITING.PUBLIC.STREAMLIT_STAGE TO ROLE SYSADMIN;

-- ── Done ─────────────────────────────────────────────────────────────────────
-- Next step: run  snow streamlit deploy  from the project root.
SELECT 'Setup complete — ready for snow streamlit deploy' AS status;
