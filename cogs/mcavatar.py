import logging
import os
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from adapters import DiscordContext
from core.commands.mcavatar.command import McAvatarCommand
from core.commands.mcavatar.service import (
    AvatarProcessingError,
    McAvatarOptions,
    McAvatarService,
)
from utils.i18n import locale_for, t

logger = logging.getLogger(__name__)

CORE_SCRIPTS_DIR = os.getenv(
    "CORE_SCRIPTS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "CORE", "scripts"),
)
SCRIPT_PATH = Path(CORE_SCRIPTS_DIR) / "process_avatar.js"


class MinecraftAvatarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = McAvatarService(SCRIPT_PATH)
        self.cmd = McAvatarCommand(self.service)

    @app_commands.command(
        name="mcavatar",
        description=locale_str(
            "Generate a pixel-style Minecraft avatar with optional effects",
            i18n_key="mcavatar.command_description",
        ),
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        player=locale_str(
            "Minecraft username to use (optional if image is provided)",
            i18n_key="mcavatar.param.player",
        ),
        image=locale_str(
            "Skin image attachment (optional if player is provided)",
            i18n_key="mcavatar.param.image",
        ),
        scale=locale_str(
            "Final upscale factor (default 10)",
            i18n_key="mcavatar.param.scale",
        ),
        outline=locale_str(
            "Outline pixel width: 0=off, 1=1px, 2=2px",
            i18n_key="mcavatar.param.outline",
        ),
        outline_color=locale_str(
            "Outline color: auto / auto_darker / auto_lighter or hex (#000000)",
            i18n_key="mcavatar.param.outline_color",
        ),
        bg_color=locale_str(
            "Background color: auto / auto_lighter / auto_darker or hex (#ffffff)",
            i18n_key="mcavatar.param.bg_color",
        ),
        fill_background=locale_str(
            "Whether to fill the background",
            i18n_key="mcavatar.param.fill_background",
        ),
        upscale48=locale_str(
            "Upscale to 48x48 scaling",
            i18n_key="mcavatar.param.upscale48",
        ),
        average_color=locale_str(
            "Average color for auto outline/bg: hex (#ff0000) or auto",
            i18n_key="mcavatar.param.average_color",
        ),
    )
    @app_commands.choices(
        outline=[
            app_commands.Choice(
                name=locale_str("0px", i18n_key="mcavatar.choice.outline_0px"),
                value=0,
            ),
            app_commands.Choice(
                name=locale_str("1px", i18n_key="mcavatar.choice.outline_1px"),
                value=1,
            ),
            app_commands.Choice(
                name=locale_str("2px", i18n_key="mcavatar.choice.outline_2px"),
                value=2,
            ),
        ]
    )
    async def mcavatar(
        self,
        interaction: discord.Interaction,
        player: Optional[str] = None,
        image: Optional[discord.Attachment] = None,
        scale: int = 10,
        outline: int = 2,
        outline_color: str = "auto",
        bg_color: str = "auto",
        fill_background: bool = True,
        upscale48: bool = True,
        average_color: Optional[str] = None,
    ):
        env_ok, env_reason = self.service.check_environment()
        if not env_ok:
            await interaction.response.send_message(
                f"❌ Unable to process avatar: Missing server dependency ({env_reason}). Please contact the admin.",
                ephemeral=True,
            )
            return

        if not player and not image:
            await interaction.response.send_message(
                t("mcavatar.error.need_player_or_image", locale=locale_for(interaction)),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        locale = locale_for(interaction)
        ctx = DiscordContext(interaction)

        image_data: Optional[bytes] = None
        if image:
            if not image.content_type or not image.content_type.startswith("image/"):
                await interaction.followup.send(
                    t("mcavatar.error.invalid_image", locale=locale),
                    ephemeral=True,
                )
                return
            image_data = await image.read()

        avg = None
        if average_color and average_color.lower() != "auto":
            try:
                hex_str = average_color.lstrip("#")
                if len(hex_str) == 3:
                    hex_str = "".join(c * 2 for c in hex_str)
                if len(hex_str) != 6:
                    raise ValueError("Invalid hex length")
                avg = {
                    "r": int(hex_str[0:2], 16),
                    "g": int(hex_str[2:4], 16),
                    "b": int(hex_str[4:6], 16),
                }
            except Exception:
                await interaction.followup.send(
                    t("mcavatar.error.invalid_average_color", locale=locale),
                    ephemeral=True,
                )
                return

        options = McAvatarOptions(
            scale=scale,
            outline=outline,
            outline_color=outline_color,
            bg_color=bg_color,
            fill_background=fill_background,
            upscale48=upscale48,
            average_color=avg,
        )

        player_display = player or t("mcavatar.attachment_label", locale=locale)
        success_content = t("mcavatar.success", locale=locale, player=player_display)

        try:
            await self.cmd.execute(
                ctx,
                player=player,
                image_data=image_data,
                options=options,
                success_content=success_content,
            )
        except AvatarProcessingError as e:
            await interaction.followup.send(
                t("mcavatar.error.processing", locale=locale, error=e),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                t("mcavatar.error.fetch_skin", locale=locale, error=e)
                if image_data is None
                else t("mcavatar.error.unexpected", locale=locale, error=e),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    service = McAvatarService(SCRIPT_PATH)
    is_valid, reason = service.check_environment()
    if not is_valid:
        logger.warning(f"Skipping loading cogs.mcavatar: {reason}")
        return

    await bot.add_cog(MinecraftAvatarCog(bot))
