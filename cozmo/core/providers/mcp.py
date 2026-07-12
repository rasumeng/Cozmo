"""MCP provider — persistent server connections in a background event loop."""

import asyncio
import time
import threading
from ..mcp_host import MCPHost
from . import Provider


class MCPManager(Provider):
    """Manages long-lived MCP connections and registers tools in the ToolRegistry.

    Extends Provider base class. Connects on startup, keeps connections alive
    across chat sessions, supports health checks and per-server reconnect.
    """

    def __init__(self, registry):
        self._registry = registry
        self._hosts: dict[str, MCPHost] = {}
        self._server_configs: dict[str, dict] = {}
        self._server_tools: dict[str, list[dict]] = {}
        self._server_startup_time: dict[str, float] = {}
        self._server_last_ping: dict[str, float] = {}
        self._server_response_time: dict[str, float] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._server_names: set[str] = set()

    def start(self, config: dict, registry=None) -> None:
        """Connect all configured MCP servers in a background event loop."""
        if registry is not None:
            self._registry = registry
        servers = config.get("mcp", {}).get("servers", {})
        if not servers:
            return
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

        future = asyncio.run_coroutine_threadsafe(
            self._connect_all(servers), self._loop
        )
        future.result()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _connect_all(self, servers: dict) -> None:
        for name, cfg in servers.items():
            await self._connect_one(name, cfg)

    async def _connect_one(self, name: str, cfg: dict) -> None:
        try:
            now = time.time()
            host = MCPHost({"servers": {name: cfg}})
            await host.connect({name: cfg})
            self._hosts[name] = host
            self._server_configs[name] = cfg
            self._server_names.add(name)
            self._server_startup_time[name] = now
            self._server_last_ping[name] = now
            wrappers = await host.get_tool_wrappers()
            tools: list[dict] = []
            for w in wrappers:
                tools.append({"name": w.__name__, "description": w.__doc__ or ""})
                sync_fn = self._make_sync(w)
                self._registry.register(w.__name__, sync_fn, w.__doc__)
            self._server_tools[name] = tools
        except Exception:
            self._server_tools[name] = []

    def _make_sync(self, async_fn):
        def sync_fn(**kwargs):
            future = asyncio.run_coroutine_threadsafe(
                async_fn(**kwargs), self._loop
            )
            return future.result()
        return sync_fn

    # ── status ──────────────────────────────────────────────────

    def get_status(self) -> dict[str, dict]:
        """Return per-server status with tools list.

        Returns:
            {"servers": {"github": {"status": "ok", "tools": [{"name":..., "description":...}]}}}
        """
        if not self._loop or self._loop.is_closed():
            return {
                n: {"status": "disconnected", "tools": self._server_tools.get(n, [])}
                for n in list(self._server_names) or list(self._server_tools.keys())
            }
        future = asyncio.run_coroutine_threadsafe(
            self._get_status(), self._loop
        )
        return future.result()

    async def _get_status(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for name in self._server_names:
            host = self._hosts.get(name)
            if not host:
                result[name] = {"status": "disconnected", "tools": self._server_tools.get(name, [])}
                continue
            try:
                await host.get_tool_wrappers()
                result[name] = {"status": "ok", "tools": self._server_tools.get(name, [])}
            except Exception:
                result[name] = {"status": "error", "tools": self._server_tools.get(name, [])}
        return result

    # ── server detail ───────────────────────────────────────────

    def get_server_detail(self, name: str) -> dict | None:
        """Return rich per-connector detail with diagnostics.

        Returns None if server not found.
        """
        cfg = self._server_configs.get(name)
        if cfg is None:
            return None
        if not self._loop or self._loop.is_closed():
            stats = "disconnected"
        else:
            future = asyncio.run_coroutine_threadsafe(
                self._probe_server(name), self._loop
            )
            try:
                stats = future.result()
            except Exception:
                stats = "error"
        startup = self._server_startup_time.get(name)
        last_ping = self._server_last_ping.get(name)
        from datetime import datetime, timezone
        return {
            "name": name,
            "status": stats,
            "tools": self._server_tools.get(name, []),
            "config": {
                "command": cfg.get("command", ""),
                "args": cfg.get("args", []),
                "env": cfg.get("env", {}),
            },
            "diagnostics": {
                "transport": "stdio",
                "startup_time_ms": round((time.time() - startup) * 1000) if startup else None,
                "last_connected": datetime.fromtimestamp(startup, tz=timezone.utc).isoformat() if startup else None,
                "last_ping": datetime.fromtimestamp(last_ping, tz=timezone.utc).isoformat() if last_ping else None,
                "response_time_ms": self._server_response_time.get(name),
            },
        }

    async def _probe_server(self, name: str) -> str:
        host = self._hosts.get(name)
        if not host:
            return "disconnected"
        try:
            t0 = time.time()
            await host.get_tool_wrappers()
            elapsed = (time.time() - t0) * 1000
            self._server_response_time[name] = round(elapsed, 1)
            self._server_last_ping[name] = time.time()
            return "ok"
        except Exception:
            return "error"

    # ── health_check ────────────────────────────────────────────

    def health_check(self) -> dict[str, str]:
        if not self._loop or self._loop.is_closed():
            return {n: "disconnected" for n in self._server_names}
        future = asyncio.run_coroutine_threadsafe(
            self._health_check(), self._loop
        )
        return future.result()

    async def _health_check(self) -> dict[str, str]:
        status: dict[str, str] = {}
        for name in self._server_names:
            host = self._hosts.get(name)
            if not host:
                status[name] = "disconnected"
                continue
            try:
                t0 = time.time()
                await host.get_tool_wrappers()
                elapsed = (time.time() - t0) * 1000
                self._server_response_time[name] = round(elapsed, 1)
                self._server_last_ping[name] = time.time()
                status[name] = "ok"
            except Exception:
                status[name] = "error"
        return status

    # ── reconnect ───────────────────────────────────────────────

    def reconnect(self, server_name: str) -> bool:
        if not self._loop or self._loop.is_closed():
            return False
        cfg = self._server_configs.get(server_name)
        if not cfg:
            return False
        future = asyncio.run_coroutine_threadsafe(
            self._reconnect_one(server_name, cfg), self._loop
        )
        return future.result()

    async def _reconnect_one(self, name: str, cfg: dict) -> bool:
        host = self._hosts.pop(name, None)
        if host:
            try:
                await host.disconnect()
            except Exception:
                pass
        for tname in list(self._registry.list()):
            if tname.name.startswith(f"{name}_"):
                self._registry.unregister(tname.name)
        try:
            await self._connect_one(name, cfg)
            return True
        except Exception:
            return False

    # ── refresh (re-discover tools) ─────────────────────────────

    def refresh(self) -> None:
        if not self._loop or self._loop.is_closed():
            return
        future = asyncio.run_coroutine_threadsafe(
            self._refresh_tools(), self._loop
        )
        future.result()

    async def _refresh_tools(self) -> None:
        for name in self._server_names:
            host = self._hosts.get(name)
            if not host:
                continue
            try:
                wrappers = await host.get_tool_wrappers()
                tools: list[dict] = []
                for w in wrappers:
                    tools.append({"name": w.__name__, "description": w.__doc__ or ""})
                    sync_fn = self._make_sync(w)
                    self._registry.register(w.__name__, sync_fn, w.__doc__)
                self._server_tools[name] = tools
            except Exception:
                pass

    # ── refresh_from_config — react to Settings save ────────────

    def refresh_from_config(self, config: dict) -> None:
        new_servers = config.get("mcp", {}).get("servers", {})
        new_names = set(new_servers.keys())
        current_names = set(self._server_names)

        to_add = new_names - current_names
        to_remove = current_names - new_names
        to_check = new_names & current_names

        for name in to_remove:
            self._disconnect_server(name)

        for name in to_add:
            self._connect_server(name, new_servers[name])

        for name in to_check:
            old_cfg = self._server_configs.get(name, {})
            new_cfg = new_servers[name]
            if old_cfg != new_cfg:
                self._reconnect_server(name, new_cfg)

    def _connect_server(self, name: str, cfg: dict) -> None:
        if not self._loop or self._loop.is_closed():
            return
        future = asyncio.run_coroutine_threadsafe(
            self._connect_one(name, cfg), self._loop
        )
        future.result()

    def _disconnect_server(self, name: str) -> None:
        if not self._loop or self._loop.is_closed():
            return
        future = asyncio.run_coroutine_threadsafe(
            self._disconnect_one(name), self._loop
        )
        future.result()

    def _reconnect_server(self, name: str, cfg: dict) -> None:
        if not self._loop or self._loop.is_closed():
            return
        future = asyncio.run_coroutine_threadsafe(
            self._reconnect_one(name, cfg), self._loop
        )
        future.result()

    async def _disconnect_one(self, name: str) -> None:
        host = self._hosts.pop(name, None)
        if host:
            try:
                await host.disconnect()
            except Exception:
                pass
        self._server_names.discard(name)
        self._server_configs.pop(name, None)
        self._server_tools.pop(name, None)
        self._server_startup_time.pop(name, None)
        self._server_last_ping.pop(name, None)
        self._server_response_time.pop(name, None)
        for tname in list(self._registry.list()):
            if tname.name.startswith(f"{name}_"):
                self._registry.unregister(tname.name)

    # ── stop ────────────────────────────────────────────────────

    def stop(self) -> None:
        if not self._loop or self._loop.is_closed():
            return
        future = asyncio.run_coroutine_threadsafe(
            self._disconnect_all(), self._loop
        )
        future.result()
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread:
            self._loop_thread.join(timeout=5)

    async def _disconnect_all(self) -> None:
        for name, host in self._hosts.items():
            try:
                await host.disconnect()
            except Exception:
                pass
        self._hosts.clear()
        self._server_configs.clear()
        self._server_tools.clear()
        self._server_startup_time.clear()
        self._server_last_ping.clear()
        self._server_response_time.clear()
        self._server_names.clear()