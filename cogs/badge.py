import asyncio
import base64
import json
import logging
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from utils.i18n import locale_for, t

logger = logging.getLogger(__name__)

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "badge.mjs"
MAX_SVG_CODE_BLOCK = 1800


class BadgeProcessingError(Exception):
    pass


def check_node_environment() -> tuple[bool, str]:
    """Check whether Node.js runtime and the badge renderer script exist."""
    if not shutil.which("node"):
        return False, "Node.js executable not found in system PATH"
    if not SCRIPT_PATH.exists():
        return False, f"Script file not found at '{SCRIPT_PATH}'"
    return True, ""


def _coerce(value: str):
    """Coerce a key=value string from `extra` into a bool/int/float/list/str."""
    s = value.strip()
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if "," in s:
        return [_coerce(part) for part in s.split(",")]
    if s.lstrip("-").isdigit():
        return int(s)
    try:
        return float(s)
    except ValueError:
        return s


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
        name=locale_str("theSVG", i18n_key="badge.choice.icon_thesvg"),
        value="thesvg",
    ),
]


def _build_config(
    top_text: str,
    bottom_text: str,
    style: Optional[app_commands.Choice[str]],
    preset_key: Optional[str],
    logo_position: Optional[app_commands.Choice[str]],
    show_disk: bool,
    icon_mode: Optional[app_commands.Choice[str]],
    fa_icon: Optional[str],
    extra: Optional[str],
) -> dict:
    cfg = {
        "topText": top_text,
        "bottomText": bottom_text,
        "showDisk": show_disk,
    }

    if style:
        cfg["style"] = style.value
    if preset_key:
        cfg["presetKey"] = preset_key.strip().lower()
    if logo_position:
        cfg["logoPosition"] = logo_position.value

    mode = icon_mode.value if icon_mode else "preset"
    if mode == "fontawesome":
        cfg["iconMode"] = "fontawesome"
        cfg["faIconClass"] = (fa_icon or "fa-brands fa-github").strip()
    elif mode == "thesvg":
        cfg["iconMode"] = "thesvg"
    else:
        cfg["iconMode"] = "preset"

    if extra:
        for pair in extra.split():
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            cfg[key.strip()] = _coerce(value)

    return cfg


async def render_badge_nodejs(config: dict) -> tuple[bytes, str, Optional[int], Optional[int]]:
    """Invoke the Node.js renderer, returning (png_bytes, svg, width, height)."""
    config_json = json.dumps(config, ensure_ascii=False)

    proc = await asyncio.create_subprocess_exec(
        "node",
        str(SCRIPT_PATH),
        config_json,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode(errors="replace").strip() or "Unknown Node.js error"
        raise BadgeProcessingError(f"renderer failed: {error_msg}")

    try:
        data = json.loads(stdout.decode("utf-8"))
    except Exception as e:
        raise BadgeProcessingError(f"invalid renderer output: {e}") from e

    png_b64 = data.get("png")
    if not png_b64:
        raise BadgeProcessingError("renderer returned no PNG data")

    png_bytes = base64.b64decode(png_b64)
    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BadgeProcessingError("renderer returned invalid PNG data")

    return png_bytes, data.get("svg") or "", data.get("width"), data.get("height")


class BadgeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="badge",
        description=locale_str(
            "Generate a Devins-style badge",
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
            "Extra options as key=value pairs, e.g. bgStops=#e05a47,#1b1412 useTextGrad=true",
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
        env_ok, env_reason = check_node_environment()
        if not env_ok:
            await interaction.response.send_message(
                t(
                    "badge.error.node",
                    locale=locale_for(interaction),
                    reason=env_reason,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        locale = locale_for(interaction)

        config = _build_config(
            top_text,
            bottom_text,
            style,
            preset_key,
            logo_position,
            show_disk,
            icon_mode,
            fa_icon,
            extra,
        )

        try:
            png_bytes, svg, width, height = await render_badge_nodejs(config)
        except BadgeProcessingError as e:
            await interaction.followup.send(
                t("badge.error.processing", locale=locale, error=e),
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.followup.send(
                t("badge.error.unexpected", locale=locale, error=e),
                ephemeral=True,
            )
            return

        files = [discord.File(BytesIO(png_bytes), filename="badge.png")]

        size_info = f" {width}x{height}" if width and height else ""
        content = t("badge.result", locale=locale, size=size_info)

        if svg and len(svg) <= MAX_SVG_CODE_BLOCK:
            content += "\n```svg\n" + svg + "\n```"
        elif svg:
            files.append(
                discord.File(BytesIO(svg.encode("utf-8")), filename="badge.svg")
            )

        try:
            await interaction.followup.send(content=content, files=files)
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.followup.send(
                t("badge.error.unexpected", locale=locale, error=e),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    ok, reason = check_node_environment()
    if not ok:
        logger.warning("Skipping loading cogs.badge: %s", reason)
        return

    await bot.add_cog(BadgeCog(bot))