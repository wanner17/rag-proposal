from __future__ import annotations

import asyncio
import logging

import httpx

from app.core.config import settings
from app.models.project_schemas import ProjectSourceConfig

logger = logging.getLogger(__name__)

CheckoutStatus = str  # "idle" | "running" | "done" | "error"

_checkout_state: dict[str, dict] = {}


def get_checkout_status(project_slug: str) -> dict:
    return _checkout_state.get(
        project_slug, {"status": "idle", "message": "", "progress": 0}
    )


def _set_status(project_slug: str, status: str, message: str, progress: int = 0) -> None:
    _checkout_state[project_slug] = {
        "status": status,
        "message": message,
        "progress": progress,
    }


async def run_checkout(project_slug: str, config: ProjectSourceConfig) -> None:
    """호스트의 checkout-server.py 웹훅을 호출해 VPN+SVN 체크아웃을 트리거한다."""
    if _checkout_state.get(project_slug, {}).get("status") == "running":
        raise RuntimeError("이미 체크아웃이 진행 중입니다.")

    _set_status(project_slug, "running", "호스트에 체크아웃 요청 중...", 10)

    webhook_url = f"{settings.SVN_CHECKOUT_WEBHOOK_URL.rstrip('/')}/checkout/{project_slug}"
    payload = {
        "svn_url": config.svn_url,
        "repo_root": config.repo_root,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)

        if resp.status_code == 409:
            _set_status(project_slug, "running", "호스트에서 이미 실행 중", 20)
            logger.info(f"[SVN] host already running checkout for {project_slug}")
            asyncio.create_task(_poll_status(project_slug))
            return

        if resp.status_code != 200:
            raise RuntimeError(f"Webhook returned {resp.status_code}: {resp.text}")

        _set_status(project_slug, "running", "호스트에서 VPN+SVN 실행 중...", 20)
        logger.info(f"[SVN] checkout triggered for {project_slug}")
        asyncio.create_task(_poll_status(project_slug))

    except httpx.RequestError as exc:
        msg = (
            "호스트 checkout-server 연결 실패: "
            f"{settings.SVN_CHECKOUT_WEBHOOK_URL} 에 접속할 수 없습니다. "
            "호스트에서 scripts/checkout-server.py가 8089 포트로 실행 중인지, "
            "또는 SVN_CHECKOUT_WEBHOOK_URL 설정이 실제 주소와 맞는지 확인하세요. "
            f"원인: {exc}"
        )
        _set_status(project_slug, "error", msg, 0)
        logger.error(f"[SVN] {msg}")


async def _poll_status(project_slug: str) -> None:
    """호스트 서버를 폴링해 완료 여부를 감지한다."""
    status_url = f"{settings.SVN_CHECKOUT_WEBHOOK_URL.rstrip('/')}/status/{project_slug}"
    max_wait = 3600
    interval = 5
    elapsed = 0

    async with httpx.AsyncClient(timeout=5) as client:
        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            try:
                resp = await client.get(status_url)
                if resp.status_code != 200:
                    continue
                payload = resp.json()
                host_status = payload.get("status")
                host_message = payload.get("message")
                if host_status in {"done", "idle"}:
                    _set_status(project_slug, "done", host_message or "완료", 100)
                    logger.info(f"[SVN] checkout done: {project_slug}")
                    return
                if host_status == "error":
                    _set_status(project_slug, "error", host_message or "호스트 체크아웃 실패", 0)
                    logger.error(f"[SVN] checkout failed on host: {project_slug}: {host_message}")
                    return
                if host_status == "running":
                    _set_status(project_slug, "running", host_message or "호스트에서 VPN+SVN 실행 중...", 50)
            except httpx.RequestError:
                pass

    _set_status(project_slug, "error", "타임아웃: 호스트 응답 없음", 0)
    logger.error(f"[SVN] polling timeout for {project_slug}")
