FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY poiex_runtime ./poiex_runtime
COPY control_service ./control_service
RUN pip install --no-cache-dir .
ENV PORT=8080
CMD ["uvicorn", "control_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
