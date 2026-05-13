# GitHub Actions CI/CD Deployment

This project deploys from GitHub to the Linux server with GitHub Actions and SSH.

## Flow

1. Push to the `main` branch.
2. GitHub Actions runs `.github/workflows/deploy.yml`.
3. The action connects to the Linux server over SSH.
4. On the server, it pulls the latest code, rebuilds the Next.js frontend, restarts it with PM2, then rebuilds/restarts Docker Compose services.

```bash
cd /opt/rag-proposal
git pull origin main
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-/api}"
export NEXT_PUBLIC_RAG_ENABLED_PLUGINS="${NEXT_PUBLIC_RAG_ENABLED_PLUGINS:-proposal}"
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8088}"
cd frontend
npm ci
npm run build
pm2 reload rag-proposal-frontend --update-env || pm2 start npm --name rag-proposal-frontend -- start
pm2 save
cd /opt/rag-proposal
docker compose down
docker compose up -d --build
docker compose ps
pm2 status rag-proposal-frontend
```

## Required GitHub Repository Secrets

Create these secrets in GitHub:

| Secret | Value |
| --- | --- |
| `SERVER_HOST` | Server IP or DNS name |
| `SERVER_PORT` | SSH port, defaults to `22` when omitted |
| `SERVER_USER` | SSH deployment user |
| `SERVER_SSH_KEY` | Private SSH key for the deployment user |

Use an unprivileged deployment user when possible. Add that user to the `docker` group or grant only the required Docker permissions. Root can work if the current server is configured that way, but it increases blast radius.

## Server Prerequisites

The server should already have:

- Repository cloned at `/opt/rag-proposal`
- A server-local `.env` file at `/opt/rag-proposal/.env`
- Docker with the Compose plugin installed
- Node.js, npm, and PM2 installed on the server
- SSH public key installed in the deployment user's `~/.ssh/authorized_keys`
- Models stored outside Git under `/opt/models`

Example first-time setup:

```bash
sudo mkdir -p /opt/rag-proposal /opt/models
sudo chown -R <deploy-user>:<deploy-user> /opt/rag-proposal
git clone <repo-url> /opt/rag-proposal
cd /opt/rag-proposal
cp .env.example .env
nano .env
npm install -g pm2
```

## Secrets and Model Files

Do not commit `.env` or model files. The repository `.gitignore` excludes environment files, runtime volumes, logs, caches, and common model formats such as `.gguf`, `.safetensors`, `.bin`, and `.onnx`.

The current production `docker-compose.yml` runs backend, Qdrant, and nginx containers. The frontend is intentionally not run by Docker Compose; it is built under `/opt/rag-proposal/frontend` and served by PM2 on host port `3000`.

The nginx container proxies `/` to `host.docker.internal:3000`, so the PM2 frontend must stay available on port `3000`. It proxies `/api/` to the Docker backend service.
By default the nginx container binds host port `80`. If another service already owns port `80`, set `NGINX_HTTP_PORT` in `/opt/rag-proposal/.env` to an available host port before deploying.

The deployment workflow exports these frontend runtime/build values before `npm run build` and `pm2 reload`:

```bash
NEXT_PUBLIC_API_URL=/api
NEXT_PUBLIC_RAG_ENABLED_PLUGINS=proposal
BACKEND_URL=http://127.0.0.1:8088
```

The backend container expects LLM, embedding, and reranker services to be available from the host through `host.docker.internal`. The model files are used by the host-side service scripts and should stay under `/opt/models`, for example:

```bash
/opt/models/qwen3-8b/*.gguf
```

This keeps large model artifacts out of GitHub and avoids rebuilding Docker images when only model files change.

## Manual Deployment Check

Before relying on GitHub Actions, run the same deployment commands once on the server:

```bash
cd /opt/rag-proposal
test -f .env
test -d /opt/models
git pull origin main
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-/api}"
export NEXT_PUBLIC_RAG_ENABLED_PLUGINS="${NEXT_PUBLIC_RAG_ENABLED_PLUGINS:-proposal}"
export BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8088}"
cd frontend
npm ci
npm run build
pm2 reload rag-proposal-frontend --update-env || pm2 start npm --name rag-proposal-frontend -- start
pm2 save
cd /opt/rag-proposal
docker compose config --quiet
docker compose down
docker compose up -d --build
docker compose ps
pm2 status rag-proposal-frontend
```

If `docker compose` requires sudo for the deployment user, either configure Docker group access or adjust the server permissions. Prefer Docker group access for a dedicated deployment user over using root SSH.
