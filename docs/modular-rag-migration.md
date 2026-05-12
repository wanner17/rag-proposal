# Modular RAG Migration Runbook

## Current State
The repo now keeps the existing user-facing proposal workflow while routing proposal behavior through a plugin boundary.

- Backend plugin manifest: `plugins/proposal/plugin.yaml`
- Backend plugin code: `backend/app/plugins/proposal/backend/`
- Backend plugin runtime: `backend/app/plugin_runtime/`
- Frontend proposal implementation: `frontend/plugins/proposal/`
- Compatibility route adapter: `frontend/app/proposals/page.tsx`
- Compatibility backend shim: `backend/app/api/proposals.py`
- Compatibility frontend exports: `frontend/lib/api.ts`

## Runtime Behavior
`backend/app/main.py` registers core routers directly and proposal routes through `register_plugin_routers`.

Enabled plugins are controlled by:

```text
RAG_ENABLED_PLUGINS=proposal
NEXT_PUBLIC_RAG_ENABLED_PLUGINS=proposal
```

The first pass supports repo-local allowlisted plugins only. It does not support uploading plugins, marketplace installs, or arbitrary external import paths.

`QDRANT_COLLECTION=proposals` remains the first-pass default only to preserve existing indexed deployments. New deployments can use the domain-neutral alias:

```text
RAG_COLLECTION=rag-documents
```

## Compatibility Shims
Keep shims until these conditions are all true:

- Existing backend proposal tests pass through plugin-owned code.
- Frontend build passes with proposal imports coming from `frontend/plugins/proposal/`.
- Static boundary tests pass.
- Compose smoke checks pass for online-dev.
- Airgap manifest validation and offline verifier dry-runs pass.

Then remove:

- `backend/app/api/proposals.py`
- proposal compatibility exports from `frontend/lib/api.ts`
- any old imports pointing to `app.services.proposal_llm`

## Airgap Bundle Flow
Build images online, then package artifacts:

```sh
BUNDLE_DIR=deploy/bundles/current deploy/bundle-scripts/save-images.sh
MODEL_SOURCE_DIR=/path/to/local/models BUNDLE_DIR=deploy/bundles/current deploy/bundle-scripts/package-models.sh
BUNDLE_DIR=deploy/bundles/current deploy/bundle-scripts/package-plugin-configs.sh
BUNDLE_DIR=deploy/bundles/current deploy/bundle-scripts/package-python-wheelhouse.sh
BUNDLE_DIR=deploy/bundles/current deploy/bundle-scripts/package-frontend-artifacts.sh
```

Before installing offline:

```sh
deploy/bundle-scripts/validate-manifest.py deploy/bundles/current/manifest.json
BUNDLE_DIR=deploy/bundles/current deploy/bundle-scripts/install-airgap.sh
```

The airgap installer path must not call Docker Hub, npm registry, pip index, HuggingFace, git clone, or external APIs.
Airgap compose defaults use local `*:airgap` image names and manifest validation requires concrete checksums for every listed artifact before `docker compose up` runs.
