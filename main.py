import asyncio
import logging
import os
import sys
import traceback
from time import perf_counter

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from terminal_commands import TerminalCommandHandler
from utils.i18n import MolankoTranslator


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("molanko.bot")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, "discord_bot.env")
COGS_DIR = os.path.join(BASE_DIR, "cogs")
UTILS_DIR = os.path.join(BASE_DIR, "utils")
DATA_DIR = os.path.join(BASE_DIR, "data")

VERSION_FILE = os.path.join(BASE_DIR, "version")

if os.path.isfile(VERSION_FILE):
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        version = f.read().strip()

    os.environ["MOLANKO_BOT_VERSION"] = version
else:
    os.environ["MOLANKO_BOT_VERSION"] = "unknown"

load_dotenv(ENV_FILE)
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN not found in discord_bot.env")

intents = discord.Intents.default()


class LoggingCommandTree(app_commands.CommandTree):
    """Log application-command starts without overriding Discord interaction dispatch."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        command = interaction.command
        if command is not None:
            interaction.client._app_command_started[interaction.id] = perf_counter()
            logger.info(
                "APP_COMMAND_START name=%s user=%s id=%s",
                command.qualified_name,
                interaction.user,
                interaction.user.id,
            )
        return True


class MyBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            tree_cls=LoggingCommandTree,
        )
        self.cogs_dir = COGS_DIR
        self.utils_dir = UTILS_DIR
        self.cmd_handler = TerminalCommandHandler(self)
        self._terminal_task: asyncio.Task | None = None
        self._app_command_started: dict[int, float] = {}

    async def setup_hook(self) -> None:
        """Load extensions and start background tasks once per Bot instance."""
        # Translator must be set before sync so command localizations are applied
        await self.tree.set_translator(MolankoTranslator())
        logger.info("Command translator set")

        await self._load_cogs()

        try:
            synced = await self.tree.sync()
            logger.info("Synced %d slash command(s)", len(synced))
        except Exception:
            logger.exception("Slash command sync failed")

        self._terminal_task = asyncio.create_task(
            self.terminal_loop(),
            name="terminal-loop",
        )

    async def _load_cogs(self) -> None:
        logger.info("Loading cogs")
        if not os.path.isdir(self.cogs_dir):
            logger.warning("Cogs directory not found: %s", self.cogs_dir)
            return

        for filename in sorted(os.listdir(self.cogs_dir)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            extension = f"cogs.{filename[:-3]}"
            try:
                await self.load_extension(extension)
                logger.info("Loaded extension=%s", extension)
            except Exception:
                logger.exception("Failed loading extension=%s", extension)

    async def terminal_loop(self) -> None:
        """Read terminal commands without blocking Discord's event loop."""
        while True:
            try:
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    logger.info("Terminal input reached EOF; stopping terminal loop")
                    return

                line = line.strip()
                if not line:
                    continue

                parts = line.split(maxsplit=1)
                command = parts[0].lower()
                argument = parts[1] if len(parts) > 1 else None
                logger.info("TERMINAL_COMMAND name=%s", command)
                await self.cmd_handler.dispatch(command, argument)

            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Terminal command loop failed")

    async def close(self) -> None:
        """Cancel the terminal task before closing the Discord client."""
        terminal_task = self._terminal_task
        self._terminal_task = None

        if terminal_task and not terminal_task.done():
            if terminal_task is not asyncio.current_task():
                terminal_task.cancel()
                try:
                    await terminal_task
                except asyncio.CancelledError:
                    pass
            else:
                terminal_task.cancel()

        await super().close()

    async def on_ready(self) -> None:
        logger.info(
            "Bot ready user=%s id=%s guilds=%d",
            self.user,
            self.user.id if self.user else "unknown",
            len(self.guilds),
        )

        await self.change_presence()

    async def on_command(self, ctx: commands.Context) -> None:
        if ctx.command is not None:
            logger.info(
                "PREFIX_COMMAND name=%s user=%s id=%s",
                ctx.command.qualified_name,
                ctx.author,
                ctx.author.id,
            )

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: app_commands.Command,
    ) -> None:
        started = self._app_command_started.pop(interaction.id, None)
        elapsed = perf_counter() - started if started is not None else None

        if elapsed is None:
            logger.info(
                "APP_COMMAND_DONE name=%s user=%s id=%s",
                command.qualified_name,
                interaction.user,
                interaction.user.id,
            )
        else:
            logger.info(
                "APP_COMMAND_DONE name=%s user=%s id=%s elapsed=%.3fs",
                command.qualified_name,
                interaction.user,
                interaction.user.id,
                elapsed,
            )

    async def on_error(self, event: str, *args, **kwargs) -> None:
        logger.exception("Unhandled event error event=%s", event)

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        command_name = getattr(interaction.command, "qualified_name", "unknown")
        started = self._app_command_started.pop(interaction.id, None)
        elapsed = perf_counter() - started if started is not None else None

        if elapsed is None:
            logger.error(
                "APP_COMMAND_FAILED name=%s user=%s id=%s error=%s: %s",
                command_name,
                interaction.user,
                interaction.user.id,
                type(error).__name__,
                error,
            )
        else:
            logger.error(
                "APP_COMMAND_FAILED name=%s user=%s id=%s elapsed=%.3fs error=%s: %s",
                command_name,
                interaction.user,
                interaction.user.id,
                elapsed,
                type(error).__name__,
                error,
            )
        logger.debug("Application command traceback", exc_info=error)

        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    "❌ 命令执行出错，请查看控制台日志。\n"
                    f"错误类型：{type(error).__name__}",
                    ephemeral=True,
                )
            except Exception:
                logger.exception("Failed to send application command error response")


async def main() -> None:
    max_retries = 5
    retry_delay = 5

    for attempt in range(1, max_retries + 1):
        bot = MyBot()
        try:
            async with bot:
                await bot.start(TOKEN)
            return
        except discord.LoginFailure:
            logger.error("Invalid TOKEN; please check discord_bot.env")
            return
        except Exception:
            logger.exception(
                "Connection attempt %d/%d failed",
                attempt,
                max_retries,
            )

            if attempt == max_retries:
                logger.error("Maximum connection retries reached; exiting")
                return

            logger.info("Retrying connection in %d seconds", retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay *= 2


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
