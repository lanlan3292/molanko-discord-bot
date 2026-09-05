# cogs/whoami.py
import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from core.commands.whoami.command import WhoAmICommand
from adapters import DiscordContext


class WhoAmI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cmd = WhoAmICommand()

    @app_commands.command(
        name="whoami",
        description=locale_str("Who am I?", i18n_key="whoami.command_description"),
    )
    async def whoami(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        ctx = DiscordContext(interaction)
        await self.cmd.execute(ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(WhoAmI(bot))
