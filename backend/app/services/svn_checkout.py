from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Callable

from app.core.config import settings
from app.models.project_schemas import ProjectSourceConfig

logger = logging.getLogger(__name__)

CheckoutStatus = str  # "idle" | "running" | "done" | "error"

# 프로젝트별 체크아웃 진행 상태 (메모리 저장, 서버 재시작 시 초기화)
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


@asynccontextmanager
async def _vpn_session():
    """VPN 연결 → yield → 해제 (L2TP/IPsec: strongSwan + xl2tpd)"""
    await _vpn_up()
    try:
        yield
    finally:
        await _vpn_down()


async def _vpn_up() -> None:
    vpn_name = settings.SVN_VPN_NAME
    server_ip = settings.SVN_VPN_SERVER_IP
    gateway = settings.SVN_VPN_GATEWAY
    logger.info(f"[VPN] connecting: {vpn_name}")
    # 1) ipsec up
    await _run(["ipsec", "up", vpn_name])
    await asyncio.sleep(3)
    # 2) xl2tpd l2tp-control
    ctrl = "/var/run/xl2tpd/l2tp-control"
    with open(ctrl, "w") as f:
        f.write(f"c {vpn_name}\n")
    await asyncio.sleep(8)
    # 3) 라우팅: SVN 서버 IP → ppp0
    await _run(["ip", "route", "replace", server_ip, "via", gateway, "dev", "ppp0"])
    logger.info("[VPN] connected")


async def _vpn_down() -> None:
    vpn_name = settings.SVN_VPN_NAME
    server_ip = settings.SVN_VPN_SERVER_IP
    gateway = settings.SVN_VPN_GATEWAY
    logger.info("[VPN] disconnecting")
    ctrl = "/var/run/xl2tpd/l2tp-control"
    try:
        with open(ctrl, "w") as f:
            f.write(f"d {vpn_name}\n")
    except Exception:
        pass
    await _run(["ip", "route", "del", server_ip, "via", gateway, "dev", "ppp0"], check=False)
    await _run(["ipsec", "down", vpn_name], check=False)
    logger.info("[VPN] disconnected")


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
    """SVN 체크아웃 또는 업데이트 실행 (백그라운드 태스크용)"""
    if _checkout_state.get(project_slug, {}).get("status") == "running":
        raise RuntimeError("이미 체크아웃이 진행 중입니다.")

    _set_status(project_slug, "running", "시작 중...", 5)

    try:
        if settings.SVN_VPN_NAME:
            async with _vpn_session():
                await _do_svn(project_slug, config)
        else:
            await _do_svn(project_slug, config)
        _set_status(project_slug, "done", "완료", 100)
        logger.info(f"[SVN] checkout done: {project_slug}")
    except Exception as exc:
        msg = str(exc)
        _set_status(project_slug, "error", msg, 0)
        logger.exception(f"[SVN] checkout failed: {project_slug}")


async def _do_svn(project_slug: str, config: ProjectSourceConfig) -> None:
    repo_root = config.repo_root
    is_update = os.path.isdir(os.path.join(repo_root, ".svn"))

    if is_update:
        _set_status(project_slug, "running", "저장소 업데이트 중...", 20)
        cmd = ["svn", "update", repo_root]
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
    _set_status(project_slug, "running", "SVN 명령 실행 중..." , 50)

    output = await _run(cmd)
    logger.info(f"[SVN] output: {output[:500]}")
    _set_status(project_slug, "running", "완료 처리 중...", 90)
