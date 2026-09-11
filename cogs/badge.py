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
RENDER_TIMEOUT_SECONDS = 30
MAX_RENDERER_OUTPUT_BYTES = 8 * 1024 * 1024

# Keep this list in sync with OFFICIAL_BRAND_ICONS in badgeworks/src/icons.js.
PRESET_ICONS = (
    "github",
    "python",
    "vscode",
    "discord",
    "react",
    "docker",
    "deno",
    "rust",
    "git",
    "gitlab",
    "npm",
    "pypi",
    "spotify",
    "steam",
    "youtube",
    "twitter",
    "star",
    "terminal",
)


class BadgeProcessingError(Exception):
    pass


class BadgeValidationError(Exception):
    pass


def check_node_environment() -> tuple[bool, str]:
    """Check whether Node.js runtime and the badge renderer script exist."""
    if not shutil.which("node"):
        return False, "Node.js executable not found in system PATH"
    if not SCRIPT_PATH.exists():
        return False, f"Script file not found at '{SCRIPT_PATH}'"
    return True, ""


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
    icon: Optional[str],
    logo_position: Optional[app_commands.Choice[str]],
    show_disk: bool,
    icon_mode: Optional[app_commands.Choice[str]],
    fontawesome_icon: Optional[str],
    thesvg_slug: Optional[str],
    background_top: Optional[str],
    background_bottom: Optional[str],
    text_color: Optional[str],
    subtitle_color: Optional[str],
    logo_color: Optional[str],
    icon_size: Optional[int],
    corner_radius: Optional[int],
) -> dict:
    cfg = {
        "topText": top_text,
        "bottomText": bottom_text,
        "showDisk": show_disk,
    }

    if style:
        cfg["style"] = style.value
    if icon:
        cfg["presetKey"] = icon.strip().lower()
    if logo_position:
        cfg["logoPosition"] = logo_position.value

    explicit_mode = icon_mode.value if icon_mode else None
    provided_sources = {
        "preset": bool(icon and icon.strip()),
        "fontawesome": bool(fontawesome_icon and fontawesome_icon.strip()),
        "thesvg": bool(thesvg_slug and thesvg_slug.strip()),
    }
    selected_sources = [source for source, provided in provided_sources.items() if provided]

    if len(selected_sources) > 1:
        raise BadgeValidationError("badge.error.icon_source_conflict")
    if explicit_mode and selected_sources and selected_sources[0] != explicit_mode:
        raise BadgeValidationError("badge.error.icon_source_conflict")

    mode = explicit_mode or (selected_sources[0] if selected_sources else "preset")
    if mode == "fontawesome":
        cfg["iconMode"] = "fontawesome"
        cfg["faIconClass"] = (
            fontawesome_icon or "fa-brands fa-github"
        ).strip()
    elif mode == "thesvg":
        cfg["iconMode"] = "thesvg"
        cfg["thesvgSlug"] = (thesvg_slug or "github").strip().lower()
    else:
        cfg["iconMode"] = "preset"

    if background_top or background_bottom:
        cfg["bgStops"] = [
            background_top or "#181f29",
            background_bottom or "#0f131a",
        ]
    if text_color:
        cfg["textColor"] = text_color
    if subtitle_color:
        cfg["subtitleColor"] = subtitle_color
    if logo_color:
        cfg["logoColor"] = logo_color
        cfg["useCustomLogoColor"] = True
    if icon_size is not None:
        cfg["userLogoScale"] = icon_size
    if corner_radius is not None:
        cfg["radius"] = corner_radius

    return cfg


async def icon_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Return bundled preset icons matching the user's input."""
    del interaction
    query = current.strip().lower()
    matches = [name for name in PRESET_ICONS if query in name]
    return [app_commands.Choice(name=name, value=name) for name in matches[:25]]


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

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=RENDER_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise BadgeProcessingError(
            f"renderer timed out after {RENDER_TIMEOUT_SECONDS} seconds"
        ) from e

    if len(stdout) > MAX_RENDERER_OUTPUT_BYTES:
        raise BadgeProcessingError("renderer output exceeded the allowed size")

    if proc.returncode != 0:
        error_msg = stderr.decode(errors="replace").strip() or "Unknown Node.js error"
        raise BadgeProcessingError(f"renderer failed: {error_msg}")

    try:
        data = json.loads(stdout.decode("utf-8"))
    except Exception as e:
        raise BadgeProcessingError(f"invalid renderer output: {e}") from e

    if not isinstance(data, dict):
        raise BadgeProcessingError("renderer returned a non-object payload")

    png_b64 = data.get("png")
    if not png_b64:
        raise BadgeProcessingError("renderer returned no PNG data")

    if not isinstance(png_b64, str):
        raise BadgeProcessingError("renderer returned invalid PNG encoding")
    try:
        png_bytes = base64.b64decode(png_b64, validate=True)
    except (ValueError, TypeError) as e:
        raise BadgeProcessingError("renderer returned invalid PNG encoding") from e
    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BadgeProcessingError("renderer returned invalid PNG data")

    svg = data.get("svg") or ""
    width = data.get("width")
    height = data.get("height")
    if not isinstance(svg, str):
        raise BadgeProcessingError("renderer returned invalid SVG data")
    if width is not None and (not isinstance(width, int) or isinstance(width, bool) or width <= 0):
        raise BadgeProcessingError("renderer returned an invalid width")
    if height is not None and (not isinstance(height, int) or isinstance(height, bool) or height <= 0):
        raise BadgeProcessingError("renderer returned an invalid height")

    return png_bytes, svg, width, height


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
        icon=locale_str(
            "Bundled icon; type to search (github, discord, python, react, docker)",
            i18n_key="badge.param.icon",
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
        fontawesome_icon=locale_str(
            "Font Awesome CSS class, e.g. fa-brands fa-github",
            i18n_key="badge.param.fontawesome_icon",
        ),
        thesvg_slug=locale_str(
            "theSVG icon slug, e.g. github (used when source is theSVG)",
            i18n_key="badge.param.thesvg_slug",
        ),
        background_top=locale_str(
            "Top background color as #RRGGBB",
            i18n_key="badge.param.background_top",
        ),
        background_bottom=locale_str(
            "Bottom background color as #RRGGBB",
            i18n_key="badge.param.background_bottom",
        ),
        text_color=locale_str(
            "Title color as #RRGGBB", i18n_key="badge.param.text_color"
        ),
        subtitle_color=locale_str(
            "Subtitle color as #RRGGBB", i18n_key="badge.param.subtitle_color"
        ),
        logo_color=locale_str(
            "Icon color as #RRGGBB", i18n_key="badge.param.logo_color"
        ),
        icon_size=locale_str(
            "Icon size in pixels", i18n_key="badge.param.icon_size"
        ),
        corner_radius=locale_str(
            "Corner radius in pixels", i18n_key="badge.param.corner_radius"
        ),
    )
    @app_commands.choices(
        style=STYLE_CHOICES,
        logo_position=LOGO_POSITION_CHOICES,
        icon_mode=ICON_MODE_CHOICES,
    )
    @app_commands.autocomplete(icon=icon_autocomplete)
    async def badge(
        self,
        interaction: discord.Interaction,
        top_text: str,
        bottom_text: str,
        style: Optional[app_commands.Choice[str]] = None,
        icon: Optional[str] = None,
        logo_position: Optional[app_commands.Choice[str]] = None,
        show_disk: bool = False,
        icon_mode: Optional[app_commands.Choice[str]] = None,
        fontawesome_icon: Optional[str] = None,
        thesvg_slug: Optional[str] = None,
        background_top: Optional[str] = None,
        background_bottom: Optional[str] = None,
        text_color: Optional[str] = None,
        subtitle_color: Optional[str] = None,
        logo_color: Optional[str] = None,
        icon_size: Optional[app_commands.Range[int, 8, 96]] = None,
        corner_radius: Optional[app_commands.Range[int, 0, 64]] = None,
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

        locale = locale_for(interaction)

        try:
            config = _build_config(
                top_text,
                bottom_text,
                style,
                icon,
                logo_position,
                show_disk,
                icon_mode,
                fontawesome_icon,
                thesvg_slug,
                background_top,
                background_bottom,
                text_color,
                subtitle_color,
                logo_color,
                icon_size,
                corner_radius,
            )
        except BadgeValidationError as e:
            await interaction.response.send_message(
                t(str(e), locale=locale),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

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
