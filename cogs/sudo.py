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
DATA_DIR = os.path.join(BASE_DIR, "data")
SUDOER_FILE = os.path.join(DATA_DIR, "sudoer.json")

# Discord's message limit is 2000 characters.
# Keep some room for formatting.
MESSAGE_LIMIT = 1900

# Maximum number of messages that can be sent for one command.
MAX_MESSAGES = 5

# Maximum execution time for one PowerShell command.
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
            logger.error(
                "sudoer.json was not found: %s",
                SUDOER_FILE,
            )
            return set()

        except (OSError, json.JSONDecodeError) as exc:
            logger.error(
                "Failed to load sudoer.json: %s",
                exc,
            )
            return set()

        if not isinstance(data, list):
            logger.error(
                "sudoer.json must contain a JSON array."
            )
            return set()

        sudoers = set()

        for user_id in data:
            try:
                sudoers.add(int(user_id))
            except (TypeError, ValueError):
                logger.warning(
                    "Ignoring invalid sudoer ID: %r",
                    user_id,
                )

        return sudoers

    @staticmethod
    def _run_powershell(
        command: str,
    ) -> tuple[int, str, str]:
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
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            ),
        )

        return (
            process.returncode,
            process.stdout,
            process.stderr,
        )

    @staticmethod
    def _run_bash(
        command: str,
    ) -> tuple[int, str, str]:
        process = subprocess.run(
            [
                "bash",
                "-c",
                command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=COMMAND_TIMEOUT,
            check=False,
        )

        return (
            process.returncode,
            process.stdout,
            process.stderr,
        )

    @staticmethod
    def _split_text(
        text: str,
        limit: int = MESSAGE_LIMIT,
    ) -> list[str]:
        """
        Split plain command output into Discord-safe chunks.

        Prefer splitting at newlines so command output remains readable.
        The caller must reserve space for any formatting added afterwards.
        """
        if not text:
            return []

        chunks = []
        current = ""

        for line in text.splitlines(keepends=True):
            # A single line may itself be longer than the limit.
            if len(line) > limit:
                if current:
                    chunks.append(current)
                    current = ""

                for index in range(0, len(line), limit):
                    chunks.append(
                        line[index:index + limit]
                    )

                continue

            if len(current) + len(line) <= limit:
                current += line
            else:
                if current:
                    chunks.append(current)

                current = line

        if current:
            chunks.append(current)

        return chunks

    @classmethod
    def _build_messages(
        cls,
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> list[str]:
        """
        Build response messages while keeping Markdown code blocks intact.

        Output is split BEFORE Markdown code fences are added. This prevents
        the final safety check from splitting an already-formatted code block.
        """
        messages = []

        header = f"Exit code: `{returncode}`"

        code_block_prefix = "```text\n"
        code_block_suffix = "\n```"
        code_block_overhead = (
            len(code_block_prefix) + len(code_block_suffix)
        )
        content_limit = MESSAGE_LIMIT - code_block_overhead

        if stdout:
            stdout_chunks = cls._split_text(
                stdout,
                content_limit,
            )

            for index, chunk in enumerate(stdout_chunks):
                if index == 0:
                    messages.append(
                        f"{header}\n"
                        f"**stdout**\n"
                        f"{code_block_prefix}"
                        f"{chunk}"
                        f"{code_block_suffix}"
                    )
                else:
                    messages.append(
                        f"**stdout (continued)**\n"
                        f"{code_block_prefix}"
                        f"{chunk}"
                        f"{code_block_suffix}"
                    )

        elif stderr:
            messages.append(header)

        if stderr:
            stderr_chunks = cls._split_text(
                stderr,
                content_limit,
            )

            for index, chunk in enumerate(stderr_chunks):
                if index == 0:
                    messages.append(
                        f"**stderr**\n"
                        f"{code_block_prefix}"
                        f"{chunk}"
                        f"{code_block_suffix}"
                    )
                else:
                    messages.append(
                        f"**stderr (continued)**\n"
                        f"{code_block_prefix}"
                        f"{chunk}"
                        f"{code_block_suffix}"
                    )

        if not messages:
            messages.append(
                f"{header}\n(No output)"
            )

        # Limit the total number of messages without ever splitting a
        # formatted code block.
        if len(messages) > MAX_MESSAGES:
            messages = messages[:MAX_MESSAGES]

            notice = (
                "\n\n"
                "[Output truncated: maximum message count reached.]"
            )

            last = messages[-1]

            if last.endswith(code_block_suffix):
                available = (
                    MESSAGE_LIMIT
                    - len(notice)
                    - len(code_block_suffix)
                )

                body = last[:-len(code_block_suffix)]
                messages[-1] = (
                    body[:available]
                    + notice
                    + code_block_suffix
                )
            else:
                messages[-1] = (
                    last[:MESSAGE_LIMIT - len(notice)]
                    + notice
                )

        return messages

    @app_commands.command(
        name="sudo",
        description="Execute an administrative command.",
    )
    @app_commands.describe(
        command="Command.",
        parameter="Command parameter.",
    )

    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)

    async def sudo(
        self,
        interaction: discord.Interaction,
        command: str,
        parameter: str | None = None,
    ):
        # Check sudo permissions.
        if interaction.user.id not in self._load_sudoers():
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                #ephemeral=True,
            )

            logger.warning(
                "Unauthorized sudo attempt: "
                "user=%s id=%s command=%r parameter=%r",
                interaction.user,
                interaction.user.id,
                command,
                parameter,
            )
            return

        command = command.strip()

        # ---------------------------------------------------------
        # Bot stop
        # ---------------------------------------------------------

        if command.lower() == "stop":
            await interaction.response.send_message(
                "Stop",
                #ephemeral=True,
            )

            logger.warning(
                "Stop requested by user=%s id=%s",
                interaction.user,
                interaction.user.id,
            )

            await self.bot.close()

            return

        # ---------------------------------------------------------
        # Bash
        # ---------------------------------------------------------

        if command.lower() == "bash":
            if not parameter or not parameter.strip():
                await interaction.response.send_message(
                    "The Bash parameter cannot be empty.",
                    #ephemeral=True,
                )
                return

            parameter = parameter.strip()

            await interaction.response.defer(
                #ephemeral=True,
                thinking=True,
            )

            logger.warning(
                "Bash command requested by "
                "user=%s id=%s command=%r",
                interaction.user,
                interaction.user.id,
                parameter,
            )

            try:
                returncode, stdout, stderr = (
                    await asyncio.to_thread(
                        self._run_bash,
                        parameter,
                    )
                )

            except FileNotFoundError:
                await interaction.followup.send(
                    "Bash was not found on this system.",
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
                    "Bash command failed unexpectedly."
                )

                await interaction.followup.send(
                    "An unexpected error occurred while executing "
                    "the command. Check the bot console for details.",
                    #ephemeral=True,
                )
                return

            messages = self._build_messages(
                returncode,
                stdout,
                stderr,
            )

            # First response.
            await interaction.followup.send(
                messages[0],
                #ephemeral=True,
            )

            # Additional messages.
            for message in messages[1:]:
                await interaction.followup.send(
                    message,
                    #ephemeral=True,
                )

            return

        # ---------------------------------------------------------
        # PowerShell
        # ---------------------------------------------------------

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
                "PowerShell command requested by "
                "user=%s id=%s command=%r",
                interaction.user,
                interaction.user.id,
                parameter,
            )

            try:
                returncode, stdout, stderr = (
                    await asyncio.to_thread(
                        self._run_powershell,
                        parameter,
                    )
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

            messages = self._build_messages(
                returncode,
                stdout,
                stderr,
            )

            # First response.
            await interaction.followup.send(
                messages[0],
                #ephemeral=True,
            )

            # Additional messages.
            for message in messages[1:]:
                await interaction.followup.send(
                    message,
                    #ephemeral=True,
                )

            return

        # ---------------------------------------------------------
        # Unknown command
        # ---------------------------------------------------------

        await interaction.response.send_message(
            "Unknown command.",
            #ephemeral=True,
        )


async def setup(bot: commands.Bot):
    enable_sudo = (os.getenv("ENABLE_SUDO") or "0").strip()

    if enable_sudo.lower() not in ("1", "true"):
        logger.info("Skipping loading cogs.sudo: ENABLE_SUDO is not set to 1.")
        return

    await bot.add_cog(Sudo(bot))
    logger.warning("ENABLE_SUDO is set to 1.")
