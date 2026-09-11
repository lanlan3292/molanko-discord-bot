import asyncio
import random
import os
import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from utils.i18n import locale_for, t

max_attempts = int(os.getenv("COMMAND_PICKAPPLE_MAX_ATTEMPTS", 1))

class PickApple(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.max_attempts = max_attempts

    @app_commands.command(
        name="pickapple",
        description=locale_str("Pick an apple from the tree", i18n_key="pickapple.command_description"),
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.checks.cooldown(1, 30.0)
    async def pickapple(self, interaction: discord.Interaction):
        locale = locale_for(interaction)
        await interaction.response.defer(thinking=True)

        await interaction.edit_original_response(content=t("pickapple.step.go", locale=locale))
        await asyncio.sleep(3)

        wait_keys = [
            "pickapple.step.wait.1",
            "pickapple.step.wait.2",
            "pickapple.step.wait.3",
            "pickapple.step.wait.4",
        ]
        wait_weights = [0.3, 0.3, 0.3, 0.1]
        selected_wait_key = random.choices(wait_keys, weights=wait_weights, k=1)[0]
        await interaction.edit_original_response(content=t(selected_wait_key, locale=locale))
        await asyncio.sleep(4)

        qualities = ["common", "ripe", "golden", "rotten", "arthur", "sock", "watermelon", "air"]
        weights = [0.6, 0.2, 0.1, 0.1, 0, 0.02, 0.02, 0.1]

        max_attempts = self.max_attempts
        quality = None

        for attempt in range(1, max_attempts + 1):
            quality = random.choices(qualities, weights=weights, k=1)[0]

            if quality == "rotten":
                if max_attempts == 1:
                    base_key = "pickapple.step.rotten"
                else:
                    base_key = "pickapple.step.rotten.threw"

                if random.random() < 0.1:
                    for step in range(1, 4):
                        key = f"{base_key}.hidden.{step}"
                        await interaction.edit_original_response(
                            content=t(key, locale=locale, attempt=attempt)
                        )
                        if step == 3:
                            await asyncio.sleep(3)   # 第三步等待 3 秒
                        else:
                            await asyncio.sleep(1.5) # 前两步各等待 1.5 秒
                else:
                    key = base_key
                    await interaction.edit_original_response(
                        content=t(key, locale=locale, attempt=attempt)
                    )
                    await asyncio.sleep(2)

                if attempt < max_attempts:
                    continue
            break

        quality_names = {
            "common": t("pickapple.quality.common", locale=locale),
            "ripe": t("pickapple.quality.ripe", locale=locale),
            "golden": t("pickapple.quality.golden", locale=locale),
            "rotten": t("pickapple.quality.rotten", locale=locale),
            "arthur": t("pickapple.quality.arthur", locale=locale),
            "sock": t("pickapple.quality.sock", locale=locale),
            "watermelon": t("pickapple.quality.watermelon", locale=locale),
            "air": t("pickapple.quality.air", locale=locale),
        }
        quality_name = quality_names.get(quality, quality)

        color_map = {
            "common": discord.Color.light_gray(),
            "ripe": discord.Color.orange(),
            "golden": discord.Color.gold(),
            "rotten": discord.Color.dark_gray(),
            "arthur": discord.Color.purple(),
            "sock": discord.Color.dark_gray(),
            "watermelon": discord.Color.green(),
            "air": discord.Color.blue(),
        }
        embed_color = color_map.get(quality, discord.Color.default())

        embed = discord.Embed(
            title=t("pickapple.embed.title", locale=locale),
            description=t("pickapple.embed.description", locale=locale, quality=quality_name),
            color=embed_color,
        )
        embed.set_footer(text=t("pickapple.embed.footer", locale=locale, user=interaction.user.display_name))

        await interaction.edit_original_response(content="", embed=embed)

    @pickapple.error
    async def pickapple_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            locale = locale_for(interaction)
            await interaction.response.send_message(
                t("pickapple.error.cooldown", locale=locale, retry_after=round(error.retry_after)),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(PickApple(bot))
