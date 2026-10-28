-- Read-only access for the web app's role, web_readonly. Create the role
-- first, then run this once per database as the role that runs
-- `etymyriad load`.
--
-- Every reload drops `public` and renames a freshly built schema in its
-- place, so grants on the current objects die with them. Default
-- privileges belong to the creating role, not to a schema, so they carry
-- over to each new generation.

ALTER DEFAULT PRIVILEGES GRANT USAGE ON SCHEMAS TO web_readonly;
ALTER DEFAULT PRIVILEGES GRANT SELECT ON TABLES TO web_readonly;

GRANT USAGE ON SCHEMA public TO web_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO web_readonly;
