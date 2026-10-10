CREATE USER commerce_admin WITH PASSWORD 'commerce_admin';
CREATE USER commerce_reader WITH PASSWORD 'commerce_reader';
ALTER ROLE commerce_reader SET default_transaction_read_only = on;

CREATE DATABASE commerce OWNER commerce_admin;
GRANT CONNECT ON DATABASE commerce TO commerce_reader;

\connect commerce

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO commerce_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE commerce_admin IN SCHEMA public
    GRANT SELECT ON TABLES TO commerce_reader;
