# Neon alpha infrastructure reference

FabricAssist uses existing SQLAlchemy/Alembic support with a pooled runtime URL and direct TLS migration URL. Apply migrations before deployment and never at Render API startup. See `docs/prerelease/neon-database.md` and `docs/prerelease/deployment.md` for the exact FabricAssist procedure.
