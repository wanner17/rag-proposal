from __future__ import annotations

import asyncio
import logging
import os

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


async def _run(cmd: list[str], check: bool = True) -> str:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode(errors="replace")
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command {cmd[0]} failed (exit {proc.returncode}): {output}")
    return output


async def run_checkout(project_slug: str, config: ProjectSourceConfig) -> None:
    """SVN 체크아웃 또는 업데이트 실행 (백그라운드 태스크용).
    VPN은 호스트에서 미리 연결되어 있어야 함 (network_mode: host로 터널 공유).
    """
    if _checkout_state.get(project_slug, {}).get("status") == "running":
        raise RuntimeError("이미 체크아웃이 진행 중입니다.")

    _set_status(project_slug, "running", "시작 중...", 5)

    try:
        await _do_svn(project_slug, config)
        _set_status(project_slug, "done", "완료", 100)
        logger.info(f"[SVN] checkout done: {project_slug}")
    except Exception:
        msg_parts = []
        import traceback
        msg_parts = traceback.format_exc()
        _set_status(project_slug, "error", str(msg_parts)[:300], 0)
        logger.exception(f"[SVN] checkout failed: {project_slug}")


async def _do_svn(project_slug: str, config: ProjectSourceConfig) -> None:
    repo_root = config.repo_root
    is_update = os.path.isdir(os.path.join(repo_root, ".svn"))

    if is_update:
        _set_status(project_slug, "running", "저장소 업데이트 중...", 20)
        cmd = ["svn", "update", repo_root,
               "--username", "wanner17",
               "--password", "wanner17",
               "--no-auth-cache",
               "--non-interactive"]
    else:
        _set_status(project_slug, "running", "저장소 내려받는 중...", 20)
        cmd = [
            "svn", "checkout", config.svn_url, repo_root,
            "--username", "wanner17",
            "--password", "wanner17",
            "--no-auth-cache",
            "--non-interactive",
        ]

    logger.info(f"[SVN] {'update' if is_update else 'checkout'}: {repo_root}")
    _set_status(project_slug, "running", "SVN 명령 실행 중...", 50)

    output = await _run(cmd)
    logger.info(f"[SVN] output: {output[:500]}")
    _set_status(project_slug, "running", "완료 처리 중...", 90)
