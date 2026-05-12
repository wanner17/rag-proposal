import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import auth, chat, documents, ingest, projects
from app.plugin_runtime import enabled_plugin_metadata, register_plugin_routers
from app.services.retrieval import ensure_collection
from app.services.projects import ensure_default_project

logging.basicConfig(level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_default_project()
    await ensure_collection()
    yield


app = FastAPI(title="Generic RAG Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
if settings.ENABLE_AGENT_ORCHESTRATION:
    from app.api import agent

    app.include_router(agent.router, prefix="/api")
register_plugin_routers(app, api_prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "plugins": [plugin["id"] for plugin in enabled_plugin_metadata()]}


@app.get("/api/plugins")
async def plugins():
    return {"plugins": enabled_plugin_metadata()}
