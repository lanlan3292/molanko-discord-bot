import asyncio
import json
import logging
import os
import subprocess
import sys

import discord
from discord import app_commands
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
            with open(SUDOER_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            logger.error("sudoer.json was not found: %s", SUDOER_FILE)
            return set()
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load sudoer.json: %s", exc)
            return set()

        if not isinstance(data, list):
            logger.error("sudoer.json must contain a JSON array.")
            return set()

        sudoers = set()

        for user_id in data:
            try:
                sudoers.add(int(user_id))
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid sudoer ID: %r", user_id)

        return sudoers

    @staticmethod
    def _run_powershell(command: str) -> tuple[int, str, str]:
        process = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
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

        return process.returncode, process.stdout, process.stderr

    @staticmethod
    def _truncate_output(text: str) -> str:
        text = text.strip()

        if len(text) <= MAX_OUTPUT:
            return text

        return text[:MAX_OUTPUT] + "\n... (output truncated)"

    @app_commands.command(
        name="sudo",
        description="Execute an administrative command.",
    )
    @app_commands.describe(
        command="Command.",
        parameter="Command parameter.",
    )
    async def sudo(
        self,
        interaction: discord.Interaction,
        command: str,
        parameter: str | None = None,
    ):
        # Check permissions
        if interaction.user.id not in self._load_sudoers():
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                #ephemeral=True,
            )

            logger.warning(
                "Unauthorized sudo attempt: user=%s id=%s command=%r parameter=%r",
                interaction.user,
                interaction.user.id,
                command,
                parameter,
            )
            return

        command = command.strip()

        # Bot reboot
        if command.lower() == "reboot":
            await interaction.response.send_message(
                "Rebooting the bot...",
                #ephemeral=True,
            )

            logger.warning(
                "Bot reboot requested by user=%s id=%s",
                interaction.user,
                interaction.user.id,
            )

            await asyncio.sleep(1)

            os.execv(sys.executable, [sys.executable] + sys.argv)
            return

        # PowerShell
        if command.lower() == "powershell":
            if not parameter or not parameter.strip():
                await interaction.response.send_message(
                    "The PowerShell parameter cannot be empty.",
                    #ephemeral=True,
                )
                return

            parameter = parameter.strip()

            await interaction.response.defer(
                #ephemeral=True,
                thinking=True,
            )

            logger.warning(
                "PowerShell command requested by user=%s id=%s command=%r",
                interaction.user,
                interaction.user.id,
                parameter,
            )

            try:
                returncode, stdout, stderr = await asyncio.to_thread(
                    self._run_powershell,
                    parameter,
                )

            except FileNotFoundError:
                await interaction.followup.send(
                    "PowerShell was not found on this system.",
                    #ephemeral=True,
                )
                return

            except subprocess.TimeoutExpired:
                await interaction.followup.send(
                    f"Command execution timed out after "
                    f"{COMMAND_TIMEOUT} seconds.",
                    #ephemeral=True,
                )
                return

            except Exception:
                logger.exception(
                    "PowerShell command failed unexpectedly."
                )

                await interaction.followup.send(
                    "An unexpected error occurred while executing "
                    "the command. Check the bot console for details.",
                    #ephemeral=True,
                )
                return

            stdout = self._truncate_output(stdout)
            stderr = self._truncate_output(stderr)

            response_parts = [
                f"Exit code: `{returncode}`",
            ]

            if stdout:
                response_parts.append(
                    f"**stdout**\n```text\n{stdout}\n```"
                )

            if stderr:
                response_parts.append(
                    f"**stderr**\n```text\n{stderr}\n```"
                )

            if not stdout and not stderr:
                response_parts.append("(No output)")

            await interaction.followup.send(
                "\n\n".join(response_parts),
                #ephemeral=True,
            )
            return

        # Unknown command
        await interaction.response.send_message(
            "Unknown command.",
            #ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Sudo(bot))
