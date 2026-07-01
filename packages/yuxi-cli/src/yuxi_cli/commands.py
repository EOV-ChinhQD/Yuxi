from __future__ import annotations

import sys
import time
import webbrowser
from collections.abc import Callable

from rich.console import Console
from rich.table import Table

from yuxi_cli.client import ClientError, YuxiClient
from yuxi_cli.config import ConfigStore, Remote
from yuxi_cli.discovery import ServerCompatibilityError, ensure_server_compatible

PENDING_ERRORS = ("authorization_pending", "slow_down")


class CommandError(Exception):
    pass


def remote_add(store: ConfigStore, name: str, url: str) -> Remote:
    config = store.load()
    remote = config.set_remote(name, url)
    store.save(config)
    return remote


def remote_use(store: ConfigStore, name: str) -> Remote:
    config = store.load()
    remote = config.use_remote(name)
    store.save(config)
    return remote


def remote_list(store: ConfigStore, console: Console) -> None:
    config = store.load()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Current", width=7)
    table.add_column("Name")
    table.add_column("URL")
    table.add_column("Auth")
    for name, remote in config.remotes.items():
        table.add_row("*" if name == config.current else "", name, remote.url, "API Key" if remote.has_api_key else "-")
    console.print(table)


def remote_ping(store: ConfigStore, name: str | None, console: Console, client_factory=YuxiClient) -> None:
    config = store.load()
    remote = config.get_remote(name)
    with client_factory(remote) as client:
        data = client.health()
    console.print(f"{remote.name}: {data.get('status', 'ok')} {data.get('version', '')}".rstrip())


def login_with_api_key(
    store: ConfigStore,
    remote_name: str | None,
    api_key: str,
    console: Console,
    client_factory=YuxiClient,
) -> Remote:
    if not api_key.startswith("yxkey_"):
        raise CommandError("API Key Định dạng không hợp lệ，nên yxkey_ Bắt đầu")

    config = store.load()
    remote = config.get_remote(remote_name)
    with client_factory(remote) as client:
        _ensure_server_compatible(client, "cli.api_key_auth")
        client.me(api_key=api_key)  # Xác minh Key Nó có sẵn không

    remote.api_key = api_key
    remote.api_key_id = ""
    store.save(config)
    console.print(f"đã lưu {remote.name} của API Key。")
    return remote


def login_with_browser(
    store: ConfigStore,
    remote_name: str | None,
    no_open: bool,
    console: Console,
    *,
    client_factory=YuxiClient,
    open_browser: Callable[[str], bool] = webbrowser.open,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> Remote:
    config = store.load()
    remote = config.get_remote(remote_name)

    with client_factory(remote) as client:
        _ensure_server_compatible(client, "cli.browser_login")
        session = client.create_cli_session()
        authorize_url = client.authorize_url(session)
        console.print(f"Mã ủy quyền: {session.user_code}")
        console.print(f"Địa chỉ ủy quyền của trình duyệt: {authorize_url}")
        if not no_open:
            open_browser(authorize_url)

        deadline = monotonic() + session.expires_in
        while monotonic() < deadline:
            try:
                data = client.exchange_cli_token(session.device_code)
                api_key = data.get("secret") or ""
                api_key_meta = data.get("api_key") or {}
                if not api_key:
                    raise CommandError("Điều khiển từ xa đã không trở lại API Key secret")

                remote.api_key = api_key
                remote.api_key_id = str(api_key_meta.get("id") or "")
                store.save(config)
                console.print(f"Đã hoàn thành {remote.name} Đăng nhập trình duyệt。")
                return remote
            except ClientError as exc:
                if not _should_keep_polling(exc):
                    raise
            sleep(max(1, session.interval))

    raise CommandError("Hết thời gian ủy quyền của trình duyệt")


def _should_keep_polling(exc: ClientError) -> bool:
    """Liệu việc thử lại có nên tiếp tục trong quá trình bỏ phiếu hay không：Đang chờ cấp phép、Giới hạn hiện tại，hoặc mạng tức thời/Lỗi máy chủ。"""
    if exc.error_code in PENDING_ERRORS or str(exc).startswith(PENDING_ERRORS):
        return True
    # status_code cho None Cho biết lỗi lớp mạng；5xx Một lỗi nhất thời ở phía máy chủ，Bạn có thể thử lại。
    return exc.status_code is None or exc.status_code >= 500


def whoami(store: ConfigStore, remote_name: str | None, console: Console, client_factory=YuxiClient) -> None:
    config = store.load()
    remote = config.get_remote(remote_name)
    if not remote.api_key:
        raise CommandError(f"remote Chưa đăng nhập: {remote.name}")
    with client_factory(remote) as client:
        user = client.me()
    console.print(f"{user.get('username')} ({user.get('uid')}) - {user.get('role')}")


def status(store: ConfigStore, remote_name: str | None, console: Console, client_factory=YuxiClient) -> None:
    config = store.load()
    remote = config.get_remote(remote_name)
    with client_factory(remote) as client:
        health = client.health()
        auth = "Chưa đăng nhập"
        if remote.api_key:
            try:
                user = client.me()
                auth = f"{user.get('username')} ({user.get('uid')})"
            except ClientError:
                auth = "API Key không hợp lệ"

    table = Table(show_header=False)
    table.add_row("Remote", remote.name)
    table.add_row("URL", remote.url)
    table.add_row("Health", f"{health.get('status', 'ok')} {health.get('version', '')}".rstrip())
    table.add_row("Auth", auth)
    console.print(table)


def logout(
    store: ConfigStore,
    remote_name: str | None,
    local_only: bool,
    console: Console,
    client_factory=YuxiClient,
) -> Remote:
    config = store.load()
    remote = config.get_remote(remote_name)
    if remote.api_key and remote.api_key_id and not local_only:
        with client_factory(remote) as client:
            client.delete_api_key(remote.api_key_id)

    remote.api_key = ""
    remote.api_key_id = ""
    store.save(config)
    console.print(f"Đã thoát {remote.name}。")
    return remote


def select_login_mode(console: Console) -> str:
    console.print("Chọn phương thức đăng nhập:")
    console.print("> 1. Đăng nhập trình duyệt（Được đề xuất）")
    console.print("  2. API Key")
    if not sys.stdin.isatty():
        return "browser"
    value = input("Chỉ cần nhấn Enter và đăng nhập bằng trình duyệt của bạn，đầu vào 2 sử dụng API Key: ").strip()
    return "api_key" if value == "2" else "browser"


def _ensure_server_compatible(client: YuxiClient, required_capability: str) -> None:
    try:
        discovery = client.discovery()
    except ClientError as exc:
        raise CommandError(f"Không thể đọc máy chủ discovery，Vui lòng xác nhận rằng điều khiển từ xa là Yuxi 0.7.1 hoặc cao hơn: {exc}") from exc
    try:
        ensure_server_compatible(discovery, required_capability)
    except ServerCompatibilityError as exc:
        raise CommandError(str(exc)) from exc
