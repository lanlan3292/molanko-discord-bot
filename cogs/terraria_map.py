import logging
from io import BytesIO

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from utils.i18n import locale_for, t
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
        locale = locale_for(interaction)
        ok, reason = check_terraria_environment()
        if not ok:
            await interaction.response.send_message(
                t("terraria_map.error.unavailable", locale=locale, reason=reason),
                ephemeral=True,
            )
            return

        if not world_file.filename or not world_file.filename.lower().endswith(".wld"):
            await interaction.response.send_message(
                t("terraria_map.error.invalid_file", locale=locale),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            world_bytes = await world_file.read()
            map_bytes, filename, preview_png = await render_terraria_world_map(world_bytes)
        except Exception as exc:
            logger.exception("Terraria map conversion failed")
            await interaction.followup.send(
                t("terraria_map.error.failed", locale=locale, error=exc),
                ephemeral=True,
            )
            return

        content = t("terraria_map.success", locale=locale, file_name=filename)
        files = [
            discord.File(BytesIO(preview_png), filename="terraria_preview.png"),
            discord.File(BytesIO(map_bytes), filename=filename),
        ]
        await interaction.followup.send(content=content, files=files)


async def setup(bot: commands.Bot):
    ok, reason = check_terraria_environment()
    if not ok:
        logger.warning("Skipping loading cogs.terraria_map: %s", reason)
        return

    await bot.add_cog(TerrariaMapCog(bot))
