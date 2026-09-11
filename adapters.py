from io import BytesIO

import discord
from core.context import BotContext, UserInfo
from utils.i18n import locale_for


class DiscordContext(BotContext):
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction

    async def reply(self, text: str, **kwargs) -> None:
        if self.interaction.response.is_done():
            await self.interaction.followup.send(text, **kwargs)
        else:
            await self.interaction.response.send_message(text, **kwargs)

    async def reply_file(
        self,
        data: bytes,
        *,
        filename: str,
        content: str | None = None,
        **kwargs,
    ) -> None:
        file = discord.File(BytesIO(data), filename=filename)
        if self.interaction.response.is_done():
            await self.interaction.followup.send(content=content, file=file, **kwargs)
        else:
            await self.interaction.response.send_message(
                content=content, file=file, **kwargs
            )

    @property
    def locale(self) -> str:
        return locale_for(self.interaction)

    @property
    def user(self) -> UserInfo:
        u = self.interaction.user
        return UserInfo(
            id=str(u.id),
            name=u.name,
        )
