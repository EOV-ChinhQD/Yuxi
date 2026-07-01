from __future__ import annotations

import os
import re
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

DEFAULT_REMOTE_NAME = "local"
DEFAULT_REMOTE_URL = "http://localhost:5173"


class ConfigError(Exception):
    pass


@dataclass
class Remote:
    name: str
    url: str
    api_key: str = ""
    api_key_id: str = ""

    @classmethod
    def from_dict(cls, name: str, data: dict) -> Remote:
        return cls(
            name=name,
            url=normalize_remote_url(str(data.get("url") or "")),
            api_key=str(data.get("api_key") or ""),
            api_key_id=str(data.get("api_key_id") or ""),
        )

    @property
    def api_base_url(self) -> str:
        return f"{self.url.rstrip('/')}/api"

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


@dataclass
class Config:
    current: str = DEFAULT_REMOTE_NAME
    remotes: dict[str, Remote] = field(default_factory=dict)

    @classmethod
    def default(cls) -> Config:
        return cls(
            current=DEFAULT_REMOTE_NAME,
            remotes={DEFAULT_REMOTE_NAME: Remote(name=DEFAULT_REMOTE_NAME, url=DEFAULT_REMOTE_URL)},
        )

    def get_remote(self, name: str | None = None) -> Remote:
        remote_name = name or self.current
        remote = self.remotes.get(remote_name)
        if remote is None:
            raise ConfigError(f"remote không tồn tại: {remote_name}")
        return remote

    def set_remote(self, name: str, url: str) -> Remote:
        remote = self.remotes.get(name)
        normalized_url = normalize_remote_url(url)
        if remote is None:
            remote = Remote(name=name, url=normalized_url)
            self.remotes[name] = remote
        else:
            if remote.url != normalized_url:
                remote.api_key = ""
                remote.api_key_id = ""
            remote.url = normalized_url
        if not self.current:
            self.current = name
        return remote

    def use_remote(self, name: str) -> Remote:
        remote = self.get_remote(name)
        self.current = remote.name
        return remote


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_config_path()

    def load(self) -> Config:
        if not self.path.exists():
            return Config.default()
        try:
            data = tomllib.loads(self.path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Tệp cấu hình TOML Định dạng không hợp lệ: {self.path}") from exc

        raw_remotes = data.get("remotes") or {}
        remotes: dict[str, Remote] = {}
        for name, raw_remote in raw_remotes.items():
            if isinstance(raw_remote, dict):
                remotes[name] = Remote.from_dict(name, raw_remote)

        if not remotes:
            remotes = Config.default().remotes

        current = str(data.get("current") or DEFAULT_REMOTE_NAME)
        if current not in remotes:
            current = next(iter(remotes))
        return Config(current=current, remotes=remotes)

    def save(self, config: Config) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # để 0600 Tạo tập tin，Tránh các tập tin mới trong umask Một cửa sổ mà người khác có thể đọc nhanh sẽ xuất hiện bên dưới（Thông tin xác thực được lưu trữ ở dạng văn bản rõ ràng）。
        def _opener(path, flags):
            return os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)

        with open(self.path, "w", encoding="utf-8", opener=_opener) as fp:
            fp.write(_render_toml(config))
        # Các tập tin hiện có sẽ không được _opener Đặt lại quyền，Hội tụ lại ở đây。
        os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)


def default_config_path() -> Path:
    return Path.home() / ".yuxi" / "config.toml"


def normalize_remote_url(raw_url: str) -> str:
    value = raw_url.strip()
    if not value:
        raise ConfigError("remote URL không thể trống")
    if "://" not in value:
        value = f"http://{value}"

    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        raise ConfigError(f"remote URL không hợp lệ: {raw_url}")
    if parts.scheme not in {"http", "https"}:
        raise ConfigError("remote URL Chỉ hỗ trợ http hoặc https")

    path = parts.path.rstrip("/")
    if path == "/api":
        path = ""
    elif path.endswith("/api"):
        path = path[: -len("/api")]

    normalized = urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")
    return normalized or f"{parts.scheme}://{parts.netloc}"


def build_url(remote_url: str, path: str) -> str:
    base = normalize_remote_url(remote_url).rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def _render_toml(config: Config) -> str:
    lines = [f'current = "{_escape(config.current)}"', ""]
    for name, remote in config.remotes.items():
        lines.append(f"[remotes.{_format_key(name)}]")
        lines.append(f'url = "{_escape(remote.url)}"')
        lines.append(f'api_key = "{_escape(remote.api_key)}"')
        lines.append(f'api_key_id = "{_escape(remote.api_key_id)}"')
        lines.append("")
    return "\n".join(lines)


def _format_key(value: str) -> str:
    if re.match(r"^[A-Za-z0-9_-]+$", value):
        return value
    return f'"{_escape(value)}"'


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
