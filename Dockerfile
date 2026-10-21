FROM node:22-alpine AS frontend
WORKDIR /site/frontend
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /site
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /site/frontend/dist/ /site/backend/static/
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers"]
