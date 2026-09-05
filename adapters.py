import discord
from core.context import BotContext
from utils.i18n import locale_for


class DiscordContext(BotContext):
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction

    async def reply(self, text: str, **kwargs) -> None:
        if self.interaction.response.is_done():
            await self.interaction.followup.send(text, **kwargs)
        else:
            await self.interaction.response.send_message(text, **kwargs)

    @property
    def locale(self) -> str:
        return locale_for(self.interaction)
