# Backup and restore

RDS staging/production uses encrypted automated backups, deletion protection,
and a 14-day baseline retention. Object storage uses encryption, versioning,
lifecycle expiration, and separate durability controls.

Local proof:

```bash
make up
make migrate
make backup-restore-test
```

The drill creates a custom-format `pg_dump`, restores it into an isolated
database, verifies Alembic head and public tables, then removes drill data.
Quarterly staging drills must also restore an RDS snapshot into an isolated
network, run tenant/count/checksum sampling, verify private object references,
exercise API readiness, record RPO/RTO, and destroy the drill instance.
