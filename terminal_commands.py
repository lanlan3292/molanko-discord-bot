import asyncio
import gc
import importlib
import os
import shutil
import sys
from typing import Any, Dict, Optional


class TerminalCommandHandler:
    """Handle commands entered through the bot process stdin."""

    def __init__(self, bot) -> None:
        self.bot = bot

    # ---------- Helpers ----------

    def _get_cog_files(self) -> Dict[str, Dict[str, Any]]:
        """Return cog file metadata keyed by cog name."""
        result: Dict[str, Dict[str, Any]] = {}
        cogs_dir = self.bot.cogs_dir

        if not os.path.isdir(cogs_dir):
            return result

        for filename in os.listdir(cogs_dir):
            if filename.startswith("_"):
                continue

            if filename.endswith(".py"):
                name = filename[:-3]
                result[name] = {
                    "file": os.path.join(cogs_dir, filename),
                    "disabled": False,
                }
            elif filename.endswith(".py.disabled"):
                name = filename[:-12]
                result[name] = {
                    "file": os.path.join(cogs_dir, filename),
                    "disabled": True,
                }

        return result

    def _is_loaded(self, cog_name: str) -> bool:
        return f"cogs.{cog_name}" in self.bot.extensions

    def _clear_cog_cache(self, cog_name: str) -> None:
        """Clear a cog's import cache. This method runs in a worker thread."""
        module_prefix = f"cogs.{cog_name}"

        for module_name in list(sys.modules):
            if module_name == module_prefix or module_name.startswith(module_prefix + "."):
                sys.modules.pop(module_name, None)

        gc.collect()

        cog_info = self._get_cog_files().get(cog_name)
        if cog_info:
            pycache_dir = os.path.join(
                os.path.dirname(cog_info["file"]),
                "__pycache__",
            )
            if os.path.isdir(pycache_dir):
                try:
                    shutil.rmtree(pycache_dir)
                except OSError as exc:
                    print(f"Failed to delete {pycache_dir}: {exc}")

        importlib.invalidate_caches()

    def _clear_utils_cache(self) -> None:
        """Clear utils import caches. This method runs in a worker thread."""
        utils_dir = self.bot.utils_dir
        if not os.path.isdir(utils_dir):
            return

        for module_name in list(sys.modules):
            if module_name.startswith("utils."):
                sys.modules.pop(module_name, None)

        for root, dirs, _files in os.walk(utils_dir):
            if "__pycache__" not in dirs:
                continue

            pycache_path = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(pycache_path)
            except OSError as exc:
                print(f"Failed to delete {pycache_path}: {exc}")

        importlib.invalidate_caches()

    # ---------- Command dispatch ----------

    async def dispatch(self, cmd: str, arg: Optional[str] = None) -> None:
        commands = {
            "list": self.cmd_list,
            "reload": self.cmd_reload,
            "stop": self.cmd_stop,
            "load": self.cmd_load,
            "disable": self.cmd_disable,
            "enable": self.cmd_enable,
            "sync": self.cmd_sync,
            "help": self.cmd_help,
        }

        handler = commands.get(cmd)
        if handler is None:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")
            return

        await handler(arg) if cmd not in {"list", "sync", "help"} else await handler()

    # ---------- Commands ----------

    async def cmd_list(self) -> None:
        cog_info = await asyncio.to_thread(self._get_cog_files)
        if not cog_info:
            print("No cog files found.")
            return

        print("Cog status:")
        for name, info in sorted(cog_info.items()):
            loaded = self._is_loaded(name)
            status = ["loaded" if loaded else "unloaded"]
            status.append("disabled" if info["disabled"] else "enabled")
            print(f"  {name}: {', '.join(status)}")

    async def cmd_reload(self, arg: Optional[str] = None) -> None:
        # "reload utils" keeps the historical behavior: full reload.
        if arg == "utils":
            arg = None

        if arg is None:
            print("Reloading all cogs and utils...")
            cog_info = await asyncio.to_thread(self._get_cog_files)
            enabled_cogs = [
                name for name, info in cog_info.items() if not info["disabled"]
            ]

            for name in enabled_cogs:
                ext = f"cogs.{name}"
                if not self._is_loaded(name):
                    continue
                try:
                    await self.bot.unload_extension(ext)
                    print(f"Unloaded {ext}")
                except Exception as exc:
                    print(f"Failed unloading {ext}: {exc}")

            for name in enabled_cogs:
                await asyncio.to_thread(self._clear_cog_cache, name)

            await asyncio.to_thread(self._clear_utils_cache)

            for name in enabled_cogs:
                ext = f"cogs.{name}"
                try:
                    await self.bot.load_extension(ext)
                    print(f"Loaded {ext}")
                except Exception as exc:
                    print(f"Failed loading {ext}: {exc}")

            return

        cog_info = await asyncio.to_thread(self._get_cog_files)
        info = cog_info.get(arg)
        if info is None:
            print(f"Cog '{arg}' not found.")
            return
        if info["disabled"]:
            print(f"Cog '{arg}' is disabled. Enable it first.")
            return

        ext = f"cogs.{arg}"
        if self._is_loaded(arg):
            try:
                await self.bot.unload_extension(ext)
                print(f"Unloaded {ext}")
            except Exception as exc:
                print(f"Failed unloading {ext}: {exc}")
                return

        await asyncio.to_thread(self._clear_cog_cache, arg)

        try:
            await self.bot.load_extension(ext)
            print(f"Loaded {ext}")
        except Exception as exc:
            print(f"Failed loading {ext}: {exc}")

        await self._sync_commands("after reload")

    async def cmd_stop(self, arg: Optional[str] = None) -> None:
        if arg is None:
            print("Shutting down bot...")
            await self.bot.close()
            return

        cog_info = await asyncio.to_thread(self._get_cog_files)
        if arg not in cog_info:
            print(f"Cog '{arg}' not found.")
            return
        if not self._is_loaded(arg):
            print(f"Cog '{arg}' is not loaded.")
            return

        ext = f"cogs.{arg}"
        try:
            await self.bot.unload_extension(ext)
            print(f"Unloaded {ext}")
        except Exception as exc:
            print(f"Failed unloading {ext}: {exc}")

    async def cmd_load(self, arg: Optional[str] = None) -> None:
        if arg is None:
            print("Usage: load <module>")
            return

        cog_info = await asyncio.to_thread(self._get_cog_files)
        info = cog_info.get(arg)
        if info is None:
            print(f"Cog '{arg}' not found.")
            return
        if info["disabled"]:
            print(f"Cog '{arg}' is disabled. Use 'enable {arg}' first.")
            return
        if self._is_loaded(arg):
            print(f"Cog '{arg}' is already loaded.")
            return

        ext = f"cogs.{arg}"
        try:
            await self.bot.load_extension(ext)
            print(f"Loaded {ext}")
            await self._sync_commands()
        except Exception as exc:
            print(f"Failed loading {ext}: {exc}")

    async def cmd_disable(self, arg: Optional[str] = None) -> None:
        if arg is None:
            print("Usage: disable <module>")
            return

        cog_info = await asyncio.to_thread(self._get_cog_files)
        info = cog_info.get(arg)
        if info is None:
            print(f"Cog '{arg}' not found.")
            return
        if info["disabled"]:
            print(f"Cog '{arg}' is already disabled.")
            return

        if self._is_loaded(arg):
            ext = f"cogs.{arg}"
            try:
                await self.bot.unload_extension(ext)
                print(f"Unloaded {ext}")
            except Exception as exc:
                print(f"Failed unloading {ext}: {exc}")
                return

        try:
            await asyncio.to_thread(
                os.rename,
                info["file"],
                info["file"] + ".disabled",
            )
            print(f"Disabled '{arg}'")
        except OSError as exc:
            print(f"Failed to disable {arg}: {exc}")

    async def cmd_enable(self, arg: Optional[str] = None) -> None:
        if arg is None:
            print("Usage: enable <module>")
            return

        cog_info = await asyncio.to_thread(self._get_cog_files)
        info = cog_info.get(arg)
        if info is None:
            print(f"Cog '{arg}' not found.")
            return
        if not info["disabled"]:
            print(f"Cog '{arg}' is already enabled.")
            return

        old_path = info["file"]
        new_path = old_path[:-12] + ".py"

        try:
            await asyncio.to_thread(os.rename, old_path, new_path)
            print(f"Enabled '{arg}'")
        except OSError as exc:
            print(f"Failed to enable {arg}: {exc}")

    async def cmd_sync(self) -> None:
        await self._sync_commands()

    async def _sync_commands(self, context: str = "") -> None:
        try:
            synced = await self.bot.tree.sync()
            suffix = f" {context}" if context else ""
            print(f"Synced {len(synced)} slash command(s){suffix}")
        except Exception as exc:
            print(f"Slash sync failed{context}: {exc}")

    async def cmd_help(self) -> None:
        print(
            """
Available terminal commands:
  list                        - Show all cogs with status
  reload                      - Reload all enabled cogs and utils
  reload <module>             - Reload one cog
  stop                        - Gracefully shut down the bot
  stop <module>               - Unload one cog
  load <module>               - Load one enabled cog
  disable <module>            - Unload and disable a cog
  enable <module>             - Enable a cog (does not load it)
  sync                        - Sync slash commands
  help                        - Show this help
"""
        )
