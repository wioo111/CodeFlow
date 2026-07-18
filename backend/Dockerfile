FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY project_templates /app/project_templates
RUN mkdir -p /app/data
ENV DATABASE_URL=sqlite:////app/data/codeflow.db
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

