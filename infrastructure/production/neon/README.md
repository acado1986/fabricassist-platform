# Neon production infrastructure reference

FabricAssist uses existing SQLAlchemy/Alembic support with a pooled runtime URL and direct TLS migration URL. Apply migrations before deployment and never at Render API startup. See `docs/production/operations.md` and `docs/production/deployment.md` for the exact FabricAssist procedure.
