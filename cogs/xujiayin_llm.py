import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands
from utils.i18n import locale_for, t

class XuJiaYinLLM(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name=locale_str(
            "许家印大模型",
            i18n_key="xujiayin_llm.command_name",
        ),
        description=locale_str(
            "空模计",
            i18n_key="xujiayin_llm.command_description",
        ),
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def xujia_yin_llm(self, interaction: discord.Interaction):
        locale = locale_for(interaction)
        await interaction.response.send_message(
            t("xujiayin_llm.response", locale=locale),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(XuJiaYinLLM(bot))
