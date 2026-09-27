import asyncio

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from utils.apple_inventory import AppleInventoryStore, InventoryStoreError
from utils.i18n import locale_for, t


class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.inventory = AppleInventoryStore()

    @app_commands.command(
        name="inventory",
        description=locale_str("View your Royal Orchard inventory", i18n_key="inventory.command_description"),
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def inventory_command(self, interaction: discord.Interaction):
        locale = locale_for(interaction)
        try:
            items = await asyncio.to_thread(self.inventory.get, interaction.user.id)
        except InventoryStoreError:
            await interaction.response.send_message(
                t("inventory.error.store", locale=locale),
                ephemeral=True,
            )
            return

        if items:
            description = "\n".join(
                t(
                    "inventory.item_count",
                    locale=locale,
                    item=t(f"pickapple.quality.{item}", locale=locale),
                    count=count,
                )
                for item, count in sorted(items.items())
            )
        else:
            description = t("inventory.empty", locale=locale)

        embed = discord.Embed(
            title=t("inventory.title", locale=locale),
            description=description,
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Inventory(bot))