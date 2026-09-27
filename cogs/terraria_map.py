import logging
from io import BytesIO

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from utils.terraria_map import check_terraria_environment, render_terraria_world_map

logger = logging.getLogger(__name__)


class TerrariaMapCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="terraria_map",
        description=locale_str(
            "Convert a Terraria .wld world file into a .map file",
            i18n_key="terraria_map.command_description",
        ),
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        world_file=locale_str(
            "Terraria world file (.wld)",
            i18n_key="terraria_map.param.world_file",
        )
    )
    async def terraria_map(
        self,
        interaction: discord.Interaction,
        world_file: discord.Attachment,
    ):
        ok, reason = check_terraria_environment()
        if not ok:
            await interaction.response.send_message(
                f"❌ Terraria map conversion is unavailable: {reason}",
                ephemeral=True,
            )
            return

        if not world_file.filename or not world_file.filename.lower().endswith(".wld"):
            await interaction.response.send_message(
                "Please attach a Terraria world file with a .wld extension.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            world_bytes = await world_file.read()
            map_bytes, filename = await render_terraria_world_map(world_bytes)
        except Exception as exc:
            logger.exception("Terraria map conversion failed")
            await interaction.followup.send(
                f"❌ Failed to convert this world file: {exc}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            file=discord.File(BytesIO(map_bytes), filename=filename),
        )


async def setup(bot: commands.Bot):
    ok, reason = check_terraria_environment()
    if not ok:
        logger.warning("Skipping loading cogs.terraria_map: %s", reason)
        return

    await bot.add_cog(TerrariaMapCog(bot))
