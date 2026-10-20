-- Runs once, when the Postgres data volume is first created.
CREATE EXTENSION IF NOT EXISTS vector;

-- Separate database for the automated test suite, so tests never touch dev data.
CREATE DATABASE knowbot_test;
\connect knowbot_test
CREATE EXTENSION IF NOT EXISTS vector;
