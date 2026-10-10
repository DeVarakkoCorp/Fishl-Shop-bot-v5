"""Сервис резервного копирования базы данных и кода на GitHub."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import posixpath
import sqlite3
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

from bot.config import (
    GITHUB_BACKUP_BRANCH,
    GITHUB_BACKUP_INTERVAL_MINUTES,
    GITHUB_BACKUP_PATH,
    GITHUB_REPO,
    GITHUB_TOKEN,
)
from bot.db.engine import BASE_DIR, DB_PATH

logger = logging.getLogger(__name__)


def github_backup_enabled() -> bool:
    """Проверяет, заданы ли все необходимые переменные окружения для GitHub бэкапа."""
    return bool(GITHUB_TOKEN and GITHUB_REPO and GITHUB_BACKUP_BRANCH)


def github_api(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    """Выполняет запрос к GitHub REST API."""
    url = "https://api.github.com" + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "Fishl-Shop-Bot",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read()
        return response.status, json.loads(body.decode("utf-8")) if body else {}


def ensure_github_backup_branch() -> None:
    """Создаёт ветку бэкапов один раз, если её ещё нет."""
    owner, repo = GITHUB_REPO.split("/", 1)
    ref_path = f"/repos/{owner}/{repo}/git/ref/heads/{GITHUB_BACKUP_BRANCH}"
    try:
        github_api("GET", ref_path)
        return
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise

    default_ref = f"/repos/{owner}/{repo}/git/ref/heads/main"
    try:
        _, data = github_api("GET", default_ref)
    except urllib.error.HTTPError:
        default_ref = f"/repos/{owner}/{repo}/git/ref/heads/master"
        _, data = github_api("GET", default_ref)

    sha = data["object"]["sha"]
    github_api("POST", f"/repos/{owner}/{repo}/git/refs", {
        "ref": f"refs/heads/{GITHUB_BACKUP_BRANCH}",
        "sha": sha,
    })


def create_sqlite_backup_bytes() -> bytes | None:
    """Делает согласованный snapshot SQLite через backup API (корректно при WAL-режиме)."""
    if not DB_PATH.exists():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "orders.db"
        source = sqlite3.connect(DB_PATH)
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        return target.read_bytes()


def create_code_backup_bytes() -> bytes:
    """Создаёт ZIP-снимок исходного кода проекта (bot/, legacy/, alembic/, тесты, конфигурации)."""
    excluded_names = {
        "orders.db",
        "orders_history.db",
        "orders (2).db",
        "orders (3).db",
        "orders (4).db",
        "orders (5).db",
    }
    allowed_suffixes = {
        ".py",
        ".md",
        ".txt",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".ini",
        ".gitattributes",
        ".gitignore",
        ".mako",
    }

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "fishl_shop_code.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for source_path in sorted(BASE_DIR.rglob("*")):
                if not source_path.is_file():
                    continue
                relative = source_path.relative_to(BASE_DIR)
                # Исключаем системные папки, .git, виртуальное окружение и кэш
                if any(part in {".git", "__pycache__", ".venv", "venv", ".idea", ".vscode", "node_modules"} for part in relative.parts):
                    continue
                if source_path.name in excluded_names or source_path.suffix.lower() in {".db", ".db-wal", ".db-shm"}:
                    continue
                if source_path.suffix.lower() not in allowed_suffixes and source_path.name not in {"requirements.txt", "Dockerfile", "Procfile", "alembic.ini"}:
                    continue
                zf.write(source_path, relative.as_posix())
        return archive.read_bytes()


def upload_github_backup() -> bool:
    """Загружает согласованный snapshot БД и ZIP-снимок кода в отдельную ветку GitHub."""
    if not github_backup_enabled():
        return False

    db_content = create_sqlite_backup_bytes()
    if not db_content:
        logger.warning("GitHub backup skipped: orders.db отсутствует")
        return False

    code_content = create_code_backup_bytes()
    ensure_github_backup_branch()
    owner, repo = GITHUB_REPO.split("/", 1)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    branch = GITHUB_BACKUP_BRANCH
    root = GITHUB_BACKUP_PATH.strip("/").strip()

    code_path = posixpath.normpath(f"{root}/../code/code_{timestamp}.zip")
    uploads = [
        (f"{root}/orders_{timestamp}.db", db_content, f"Backup orders.db {timestamp}"),
        (code_path, code_content, f"Backup bot code {timestamp}"),
    ]
    for path, content, message in uploads:
        payload = {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
            "branch": branch,
        }
        github_api("PUT", f"/repos/{owner}/{repo}/contents/{path}", payload)
        logger.info("GitHub backup uploaded: %s:%s", branch, path)
    return True


async def upload_github_backup_async() -> bool:
    """Асинхронная обёртка для upload_github_backup, запускающая синхронные сетевые вызовы в потоке."""
    return await asyncio.to_thread(upload_github_backup)


async def backup_loop(interval_minutes: int | None = None) -> None:
    """Фоновый цикл создания периодических бэкапов на GitHub.

    Первый запуск через 30 секунд после старта бота, далее каждые interval_minutes минут.
    """
    if interval_minutes is None:
        interval_minutes = int(GITHUB_BACKUP_INTERVAL_MINUTES)
    interval_seconds = max(15, interval_minutes) * 60

    logger.info(
        "Фоновый бэкап на GitHub активирован (первый запуск через 30 сек, затем каждые %s мин)",
        interval_minutes,
    )
    await asyncio.sleep(30)

    while True:
        try:
            if github_backup_enabled():
                logger.info("Запуск периодического создания бэкапа...")
                ok = await upload_github_backup_async()
                if ok:
                    logger.info("Периодический GitHub-бэкап успешно загружен.")
                else:
                    logger.warning("Периодический GitHub-бэкап пропущен (orders.db отсутствует).")
            else:
                logger.debug("GitHub-бэкап отключён: отсутствуют переменные GITHUB_*.")
        except asyncio.CancelledError:
            logger.info("Цикл фонового бэкапа отменён.")
            raise
        except Exception:
            logger.exception("Ошибка при выполнении автоматического GitHub-бэкапа:")

        await asyncio.sleep(interval_seconds)
