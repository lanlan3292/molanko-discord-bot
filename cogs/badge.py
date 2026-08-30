import base64
import os
from io import BytesIO
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from utils.i18n import locale_for, t

API_URL = (os.getenv("BADGEWORKS_API_URL") or "http://localhost:8080").rstrip("/")
API_KEY = os.getenv("BADGEWORKS_API_KEY")
API_TIMEOUT = 20


STYLE_CHOICES = [
    app_commands.Choice(name="Cozy", value="cozy"),
    app_commands.Choice(name="Compact", value="compact"),
    app_commands.Choice(name="Cozy Minimal", value="cozy-minimal"),
    app_commands.Choice(name="Compact Minimal", value="compact-minimal"),
]

LOGO_POSITION_CHOICES = [
    app_commands.Choice(
        name=locale_str("Left", i18n_key="badge.choice.logo_left"), value="left"
    ),
    app_commands.Choice(
        name=locale_str("Right", i18n_key="badge.choice.logo_right"), value="right"
    ),
    app_commands.Choice(
        name=locale_str("None", i18n_key="badge.choice.logo_none"), value="none"
    ),
]

ICON_MODE_CHOICES = [
    app_commands.Choice(
        name=locale_str("Preset icon", i18n_key="badge.choice.icon_preset"),
        value="preset",
    ),
    app_commands.Choice(
        name=locale_str("FontAwesome", i18n_key="badge.choice.icon_fa"),
        value="fontawesome",
    ),
    app_commands.Choice(
        name=locale_str("No icon", i18n_key="badge.choice.icon_none"),
        value="none",
    ),
]


class BadgeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="badge",
        description=locale_str(
            "Generate a Devins Badge via the Badgeworks API",
            i18n_key="badge.command_description",
        ),
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        top_text=locale_str(
            "Top text (title)", i18n_key="badge.param.top_text"
        ),
        bottom_text=locale_str(
            "Bottom text (subtitle)", i18n_key="badge.param.bottom_text"
        ),
        style=locale_str(
            "Badge style (default Cozy)", i18n_key="badge.param.style"
        ),
        preset_key=locale_str(
            "Preset icon key, e.g. github, discord, python",
            i18n_key="badge.param.preset_key",
        ),
        logo_position=locale_str(
            "Logo position (default Left)", i18n_key="badge.param.logo_position"
        ),
        show_disk=locale_str(
            "Show a background disk behind the logo",
            i18n_key="badge.param.show_disk",
        ),
        icon_mode=locale_str(
            "Icon source (default Preset icon)",
            i18n_key="badge.param.icon_mode",
        ),
        fa_icon=locale_str(
            "FontAwesome icon class, e.g. fa-brands fa-github",
            i18n_key="badge.param.fa_icon",
        ),
        extra=locale_str(
            "Extra options as key=value pairs, e.g. bgStops=#e05a47 bgGradPreset=fire",
            i18n_key="badge.param.extra",
        ),
    )
    @app_commands.choices(
        style=STYLE_CHOICES,
        logo_position=LOGO_POSITION_CHOICES,
        icon_mode=ICON_MODE_CHOICES,
    )
    async def badge(
        self,
        interaction: discord.Interaction,
        top_text: str,
        bottom_text: str,
        style: Optional[app_commands.Choice[str]] = None,
        preset_key: Optional[str] = None,
        logo_position: Optional[app_commands.Choice[str]] = None,
        show_disk: bool = False,
        icon_mode: Optional[app_commands.Choice[str]] = None,
        fa_icon: Optional[str] = None,
        extra: Optional[str] = None,
    ):
        if not API_KEY:
            await interaction.response.send_message(
                "❌ Badgeworks API key is not configured. Contact the bot admin.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        locale = locale_for(interaction)

        params = {
            "topText": top_text,
            "bottomText": bottom_text,
            "showDisk": "true" if show_disk else "false",
        }

        if style:
            params["style"] = style.value
        if preset_key:
            params["presetKey"] = preset_key
        if logo_position:
            params["logoPosition"] = logo_position.value
        if icon_mode:
            params["iconMode"] = icon_mode.value
        if fa_icon:
            params["faIconInput"] = fa_icon

        if extra:
            for pair in extra.split():
                if "=" not in pair:
                    continue
                k, v = pair.split("=", 1)
                params[k] = v

        headers = {"X-API-Key": API_KEY}

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
            ) as session:
                async with session.get(
                    f"{API_URL}/api/badge", params=params, headers=headers
                ) as resp:
                    if resp.status == 401:
                        await interaction.followup.send(
                            t("badge.error.unauthorized", locale=locale),
                            ephemeral=True,
                        )
                        return
                    if resp.status != 200:
                        body = await resp.text()
                        await interaction.followup.send(
                            t(
                                "badge.error.api_error",
                                locale=locale,
                                status=resp.status,
                                body=body[:500],
                            ),
                            ephemeral=True,
                        )
                        return

                    data = await resp.json()

            svg = data.get("svg")
            png_b64 = data.get("png")
            width = data.get("width")
            height = data.get("height")

            if not svg:
                await interaction.followup.send(
                    t("badge.error.invalid_response", locale=locale),
                    ephemeral=True,
                )
                return

            files = []
            if png_b64:
                png_bytes = base64.b64decode(png_b64)
                files.append(
                    discord.File(BytesIO(png_bytes), filename="badge.png")
                )

            svg_block = f"```svg\n{svg}\n```"
            size_info = f" {width}x{height}" if width and height else ""

            await interaction.followup.send(
                content=t(
                    "badge.result",
                    locale=locale,
                    size=size_info,
                )
                + "\n"
                + svg_block,
                files=files,
            )

        except aiohttp.ClientError as e:
            await interaction.followup.send(
                t("badge.error.connection", locale=locale, error=e),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                t("badge.error.unexpected", locale=locale, error=e),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(BadgeCog(bot))