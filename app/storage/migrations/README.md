# P7 Storage Migrations

P7 keeps a local SQLite schema in code for deterministic validation. This
directory marks the migration boundary for future schema files when the
PostgreSQL adapter moves from schema-ready to production deployment.
