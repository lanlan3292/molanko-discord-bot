import asyncio
import base64
import json
import logging
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from utils.i18n import locale_for, t

logger = logging.getLogger(__name__)

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "process_avatar.js"


def check_node_environment() -> tuple[bool, str]:
    """Check whether Node.js runtime and dependency script exist."""
    if not shutil.which("node"):
        return False, "Node.js executable not found in system PATH"
    if not SCRIPT_PATH.exists():
        return False, f"Script file not found at '{SCRIPT_PATH}'"
    return True, ""


class AvatarProcessingError(Exception):
    pass


async def fetch_skin_from_username(username: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.mojang.com/users/profiles/minecraft/{username}"
        ) as resp:
            if resp.status != 200:
                raise ValueError(f"Player '{username}' not found")
            data = await resp.json()
            uuid = data["id"]

        async with session.get(
            f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}"
        ) as resp:
            if resp.status != 200:
                raise ValueError("Failed to fetch profile from Mojang")
            profile = await resp.json()

            textures = next(
                (prop for prop in profile.get("properties", []) if prop.get("name") == "textures"),
                None,
            )
            if not textures:
                raise ValueError("No textures found in profile")

            decoded = base64.b64decode(textures["value"]).decode("utf-8")
            texture_data = json.loads(decoded)
            skin_url = texture_data.get("textures", {}).get("SKIN", {}).get("url")
            if not skin_url:
                raise ValueError("Skin URL missing in texture data")

        async with session.get(skin_url) as resp:
            if resp.status != 200:
                raise ValueError("Failed to download skin image")
            return await resp.read()


async def process_skin_nodejs(image_data: bytes, options: dict) -> bytes:
    """Invoke Node.js subprocess to process skin image."""
    options_json = json.dumps(options)

    proc = await asyncio.create_subprocess_exec(
        "node",
        str(SCRIPT_PATH),
        options_json,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate(input=image_data)

    if proc.returncode != 0:
        error_msg = stderr.decode().strip() or "Unknown Node.js execution error"
        raise AvatarProcessingError(f"Node.js processing failed: {error_msg}")

    return stdout


class MinecraftAvatarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        env_ok, env_reason = check_node_environment()
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

        try:
            if image:
                if not image.content_type or not image.content_type.startswith("image/"):
                    await interaction.followup.send(
                        t("mcavatar.error.invalid_image", locale=locale),
                        ephemeral=True,
                    )
                    return
                image_data = await image.read()
            else:
                image_data = await fetch_skin_from_username(player)
        except Exception as e:
            await interaction.followup.send(
                t("mcavatar.error.fetch_skin", locale=locale, error=e),
                ephemeral=True,
            )
            return

        options = {
            "scale": scale,
            "outlineMode": outline,
            "outlineColor": outline_color,
            "bgColor": bg_color,
            "fillBackground": fill_background,
            "upscale48": upscale48,
        }

        if average_color and average_color.lower() != "auto":
            try:
                hex_str = average_color.lstrip("#")
                if len(hex_str) == 3:
                    hex_str = "".join(c * 2 for c in hex_str)
                if len(hex_str) != 6:
                    raise ValueError("Invalid hex length")
                r = int(hex_str[0:2], 16)
                g = int(hex_str[2:4], 16)
                b = int(hex_str[4:6], 16)
                options["averageColor"] = {"r": r, "g": g, "b": b}
            except Exception:
                await interaction.followup.send(
                    t("mcavatar.error.invalid_average_color", locale=locale),
                    ephemeral=True,
                )
                return

        try:
            result_data = await process_skin_nodejs(image_data, options)
        except AvatarProcessingError as e:
            await interaction.followup.send(
                t("mcavatar.error.processing", locale=locale, error=e),
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.followup.send(
                t("mcavatar.error.unexpected", locale=locale, error=e),
                ephemeral=True,
            )
            return

        file = discord.File(BytesIO(result_data), filename="avatar.png")
        player_display = player or t("mcavatar.attachment_label", locale=locale)
        await interaction.followup.send(
            content=t(
                "mcavatar.success",
                locale=locale,
                player=player_display,
            ),
            file=file,
        )


async def setup(bot: commands.Bot):
    is_valid, reason = check_node_environment()
    if not is_valid:
        logger.warning(f"Skipping loading cogs.mcavatar: {reason}")
        return

    await bot.add_cog(MinecraftAvatarCog(bot))
