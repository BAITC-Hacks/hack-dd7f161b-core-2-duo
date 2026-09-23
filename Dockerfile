# one image, two targets: `api` (FastAPI) and `web` (Next.js)
FROM python:3.12-slim AS api
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY career_quest ./career_quest
COPY api ./api
COPY data ./data
RUN uv pip install --python .venv/bin/python "uvicorn>=0.30"
EXPOSE 8000
CMD [".venv/bin/uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "8000"]

FROM node:22-slim AS web
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json next.config.mjs ./
COPY app ./app
COPY components ./components
COPY lib ./lib
# rewrites are resolved at build time, so the api address is baked in here
ARG API_URL=http://api:8000
ENV API_URL=$API_URL
RUN npm run build
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
