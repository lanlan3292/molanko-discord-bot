# cogs/jrrp.py
import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from adapters import DiscordContext
from commands.commands.jrrp.command import JrrpCommand
from commands.context import UserInfo


class Jrrp(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cmd = JrrpCommand()

    @app_commands.command(
        name="jrrp",
        description=locale_str(
            "Check today's luck",
            i18n_key="jrrp.command_description",
        ),
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        user=locale_str(
            "User to check (defaults to yourself)",
            i18n_key="jrrp.param.user",
        ),
    )
    async def jrrp(
        self,
        interaction: discord.Interaction,
        user: discord.User | None = None,
    ):
        await interaction.response.defer(thinking=True)

        ctx = DiscordContext(interaction)
        target: UserInfo | None = None
        if user is not None:
            target = UserInfo(
                id=str(user.id),
                name=user.name,
                username=user.name,
                display_name=user.display_name,
            )

        await self.cmd.execute(ctx, target=target)


async def setup(bot: commands.Bot):
    await bot.add_cog(Jrrp(bot))
