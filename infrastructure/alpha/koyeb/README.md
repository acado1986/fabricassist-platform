# Koyeb alpha infrastructure reference

FabricAssist deploys the existing API using `.github/workflows/deploy-alpha.yml`. The workflow is the executable configuration: Docker context `backend`, free `fra` web service, one Uvicorn worker, and no Celery or migration startup. Follow `docs/alpha/deployment.md` and `docs/alpha/secrets.md` for setup and recovery; do not store Koyeb credentials or duplicate provider configuration here.
