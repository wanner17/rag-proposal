#!/usr/bin/env python3
"""
호스트에서 실행하는 SVN 체크아웃 트리거 서버.
백엔드 컨테이너에서 POST /checkout/{project_slug} 를 호출하면
VPN 연결 → SVN checkout/update → 소스 인덱싱 API 호출까지 수행한다.

환경 변수:
  VPN_NAME              xl2tpd/ipsec 프로파일명 (없으면 VPN 생략)
  SVN_IP                SVN 서버 IP (라우팅용)
  VPN_GATEWAY           ppp0 게이트웨이 IP
  BACKEND_URL           백엔드 URL (기본: http://127.0.0.1:8088)
  SOURCE_INDEX_API_TOKEN  소스 인덱싱 Bearer 토큰

실행: python3 /opt/rag-scripts/checkout-server.py
"""
import json
import logging
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8089

VPN_NAME = os.environ.get("VPN_NAME", "")
SVN_IP = os.environ.get("SVN_IP", "")
VPN_GATEWAY = os.environ.get("VPN_GATEWAY", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8088")
SOURCE_INDEX_API_TOKEN = os.environ.get("SOURCE_INDEX_API_TOKEN", "")
SVN_USERNAME = os.environ.get("SVN_USERNAME", "wanner17")
SVN_PASSWORD = os.environ.get("SVN_PASSWORD", "wanner17")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("checkout-server")

_running: set[str] = set()
_status: dict[str, dict] = {}
_lock = threading.Lock()


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed (exit {result.returncode}): {result.stderr[-300:]}")
    return result


def _set_status(project_slug: str, status: str, message: str) -> None:
    with _lock:
        _status[project_slug] = {"status": status, "message": message}


def _vpn_connect() -> None:
    if not VPN_NAME:
        return
    logger.info("[VPN] connecting")
    _run(["ipsec", "up", VPN_NAME])
    import time; time.sleep(3)
    with open("/var/run/xl2tpd/l2tp-control", "w") as f:
        f.write(f"c {VPN_NAME}\n")
    time.sleep(8)
    if SVN_IP and VPN_GATEWAY:
        _run(["ip", "route", "replace", SVN_IP, "via", VPN_GATEWAY, "dev", "ppp0"])
    logger.info("[VPN] connected")


def _vpn_disconnect() -> None:
    if not VPN_NAME:
        return
    logger.info("[VPN] disconnecting")
    try:
        with open("/var/run/xl2tpd/l2tp-control", "w") as f:
            f.write(f"d {VPN_NAME}\n")
    except Exception:
        pass
    if SVN_IP and VPN_GATEWAY:
        _run(["ip", "route", "del", SVN_IP, "via", VPN_GATEWAY, "dev", "ppp0"], check=False)
    _run(["ipsec", "down", VPN_NAME], check=False)


def _relative_svn_path(output_path: str, repo_root: str) -> str:
    if not output_path:
        return ""
    normalized = output_path.replace("\\", "/").rstrip("/")
    if not os.path.isabs(output_path):
        repo_name = os.path.basename(os.path.abspath(repo_root))
        if normalized == repo_name:
            return ""
        prefix = f"{repo_name}/"
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
        return normalized
    repo_abs = os.path.abspath(repo_root)
    path_abs = os.path.abspath(output_path)
    try:
        return os.path.relpath(path_abs, repo_abs).replace(os.sep, "/")
    except ValueError:
        return output_path.replace("\\", "/")


def _svn_checkout_or_update(svn_url: str, repo_root: str) -> tuple[list[str], list[str], str]:
    """SVN checkout 또는 update 실행. (changed_files, deleted_files, revision) 반환."""
    import os

    svn_args = [
        "--username", SVN_USERNAME,
        "--password", SVN_PASSWORD,
        "--no-auth-cache",
        "--non-interactive",
    ]

    if os.path.isdir(os.path.join(repo_root, ".svn")):
        logger.info(f"[SVN] update: {repo_root}")
        cmd = ["svn", "update", repo_root] + svn_args
    else:
        logger.info(f"[SVN] checkout: {svn_url} -> {repo_root}")
        os.makedirs(repo_root, exist_ok=True)
        cmd = ["svn", "checkout", svn_url, repo_root] + svn_args

    result = _run(cmd)
    output = result.stdout + result.stderr

    revision = ""
    for line in output.splitlines():
        import re
        m = re.search(r"revision (\d+)|리비전 (\d+)", line)
        if m:
            revision = m.group(1) or m.group(2)

    changed, deleted = [], []
    for line in output.splitlines():
        if not line:
            continue
        status = line[0]
        if status not in ("A", "U", "G", "R", "D"):
            continue
        path = _relative_svn_path(line[1:].lstrip(), repo_root)
        if not path or path.startswith("../") or path == "..":
            logger.warning(f"[SVN] skipping path outside repo_root: {line[1:].lstrip()}")
            continue
        if status in ("A", "U", "G", "R"):
            changed.append(path)
        elif status == "D":
            deleted.append(path)

    logger.info(f"[SVN] done. changed={len(changed)} deleted={len(deleted)} revision={revision}")
    return changed, deleted, revision


def _call_source_index(project_slug: str, changed: list[str], deleted: list[str], revision: str) -> None:
    if not SOURCE_INDEX_API_TOKEN:
        logger.warning("[RAG] SOURCE_INDEX_API_TOKEN not set, skipping index call")
        return

    import urllib.request
    payload = json.dumps({
        "changed_files": changed,
        "deleted_files": deleted,
        "svn_revision": revision or None,
    }).encode()

    url = f"{BACKEND_URL}/api/project-sources/{project_slug}/source-index"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {SOURCE_INDEX_API_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            logger.info(f"[RAG] source-index response: {resp.status}")
    except Exception as exc:
        logger.error(f"[RAG] source-index call failed: {exc}")


def _run_checkout(project_slug: str, svn_url: str, repo_root: str) -> None:
    with _lock:
        if project_slug in _running:
            return
        _running.add(project_slug)
    try:
        _set_status(project_slug, "running", "VPN/SVN 작업 중")
        _vpn_connect()
        changed, deleted, revision = _svn_checkout_or_update(svn_url, repo_root)
        _set_status(project_slug, "running", "소스 색인 API 호출 중")
        _call_source_index(project_slug, changed, deleted, revision)
        _set_status(project_slug, "done", "체크아웃 및 색인 요청 완료")
        logger.info(f"[{project_slug}] checkout complete")
    except Exception as exc:
        _set_status(project_slug, "error", str(exc))
        logger.error(f"[{project_slug}] checkout failed: {exc}")
    finally:
        try:
            _vpn_disconnect()
        except Exception:
            pass
        with _lock:
            _running.discard(project_slug)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "checkout":
            project_slug = parts[1]
            body = self._read_body()
            svn_url = body.get("svn_url", "")
            repo_root = body.get("repo_root", "")

            if not svn_url or not repo_root:
                self._respond(400, {"error": "svn_url and repo_root required"})
                return

            with _lock:
                already = project_slug in _running
            if already:
                self._respond(409, {"status": "running", "message": "이미 진행 중입니다."})
                return

            _set_status(project_slug, "running", "체크아웃 대기 중")
            threading.Thread(
                target=_run_checkout,
                args=(project_slug, svn_url, repo_root),
                daemon=True,
            ).start()
            self._respond(200, {"status": "started"})
        else:
            self._respond(404, {"error": "not found"})

    def do_GET(self):
        parts = self.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "status":
            project_slug = parts[1]
            with _lock:
                running = project_slug in _running
                state = _status.get(project_slug)
            if running or (state and state.get("status") == "running"):
                self._respond(200, state or {"status": "running", "message": "진행 중입니다."})
            elif state and state.get("status") in {"done", "error"}:
                self._respond(200, state)
            else:
                self._respond(200, {"status": "idle", "message": ""})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    logger.info(f"checkout-server listening on {LISTEN_HOST}:{LISTEN_PORT}")
    server.serve_forever()
