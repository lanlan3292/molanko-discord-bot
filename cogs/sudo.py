import asyncio
import json
import logging
import os
import subprocess

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUDOER_FILE = os.path.join(BASE_DIR, "data", "sudoer.json")
MAX_OUTPUT = 1800
COMMAND_TIMEOUT = 30


class Sudo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _load_sudoers() -> set[int]:
        try:
            with open(SUDOER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.warning("sudoer file not found: %s", SUDOER_FILE)
            return set()
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load sudoers: %s", exc)
            return set()

        if not isinstance(data, list):
            logger.error("sudoer.json must contain a JSON array of Discord user IDs")
            return set()

        sudoers: set[int] = set()
        for value in data:
            try:
                sudoers.add(int(value))
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid sudoer ID: %r", value)
        return sudoers

    @staticmethod
    def _run_powershell(command: str) -> tuple[int, str, str]:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=COMMAND_TIMEOUT,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return completed.returncode, completed.stdout, completed.stderr

    @staticmethod
    def _truncate(text: str) -> str:
        text = text.strip()
        if len(text) <= MAX_OUTPUT:
            return text
        return text[:MAX_OUTPUT] + "\n... (output truncated)"

    @app_commands.command(
        name="sudo",
        description=locale_str(
            "Run a PowerShell command with sudo permission",
            i18n_key="sudo.command_description",
        ),
    )
    @app_commands.describe(command="PowerShell command to execute; use 'reboot' to restart the host")
    async def sudo(self, interaction: discord.Interaction, command: str):
        if interaction.user.id not in self._load_sudoers():
            await interaction.response.send_message(
                "❌ 你没有使用 /sudo 的权限。",
                ephemeral=True,
            )
            logger.warning(
                "Unauthorized sudo attempt user=%s id=%s command=%r",
                interaction.user,
                interaction.user.id,
                command,
            )
            return

        command = command.strip()
        if not command:
            await interaction.response.send_message("❌ 命令不能为空。", ephemeral=True)
            return

        if command.lower() == "reboot":
            command = "Restart-Computer -Force"

        await interaction.response.defer(ephemeral=True, thinking=True)
        logger.warning(
            "SUDO_EXEC user=%s id=%s command=%r",
            interaction.user,
            interaction.user.id,
            command,
        )

        try:
            returncode, stdout, stderr = await asyncio.to_thread(
                self._run_powershell,
                command,
            )
        except FileNotFoundError:
            await interaction.followup.send(
                "❌ 找不到 powershell.exe；此功能需要在 Windows 主机上运行。",
                ephemeral=True,
            )
            return
        except subprocess.TimeoutExpired:
            await interaction.followup.send(
                f"⏱️ 命令执行超过 {COMMAND_TIMEOUT} 秒，已终止。",
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("Sudo command failed unexpectedly")
            await interaction.followup.send(
                "❌ 执行命令时发生异常，请查看机器人控制台日志。",
                ephemeral=True,
            )
            return

        output = self._truncate(stdout)
        error = self._truncate(stderr)
        parts = [f"退出码：`{returncode}`"]
        if output:
            parts.append(f"**stdout**\n```text\n{output}\n```")
        if error:
            parts.append(f"**stderr**\n```text\n{error}\n```")
        if not output and not error:
            parts.append("（无输出）")

        await interaction.followup.send("\n\n".join(parts), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Sudo(bot))
