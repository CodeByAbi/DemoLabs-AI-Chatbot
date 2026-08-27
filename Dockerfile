FROM nawainternal.azurecr.io/lab/orchestrator:base

COPY --chown=appuser:appuser ./app /app/app

EXPOSE 8000