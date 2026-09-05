# cogs/version.py
import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from core.commands.version.command import VersionCommand
from adapters import DiscordContext


class Version(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cmd = VersionCommand()

    @app_commands.command(
        name="version",
        description=locale_str(
            "Show the bot version",
            i18n_key="version.command_description",
        ),
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def version(self, interaction: discord.Interaction):
        ctx = DiscordContext(interaction)
        await self.cmd.execute(ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(Version(bot))
