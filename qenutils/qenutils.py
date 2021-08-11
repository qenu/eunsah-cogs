import os
from typing import Literal, Optional

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

class Qenutils(commands.Cog):
    """
    Utility cogs from qenu
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=164900704526401545003,
            force_registration=True,
        )

        # self.config.register_global(**default_global)

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @commands.command(name='ocr')
    @commands.admin_or_permissions(manage_roles=True)
    async def ocr(self, ctx: commands.Context, link: Optional[str]):

        GOOGLE_APPLICATION_CREDENTIALS = await self.bot.get_shared_api_tokens("google_application_credentials")
        if GOOGLE_APPLICATION_CREDENTIALS.get("path") is None:
            return await ctx.send("The Service Account file path has not been set. See `[p]ocrset path`")

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"]= GOOGLE_APPLICATION_CREDENTIALS

        try:
            if link is None:
                try:
                    link = ctx.message.attachments[0].url
                except:
                    link = None
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()
            response = client.annotate_image(
                {'image' : {'source' : {'image_uri' : link}},}
            )
            texts = response.text_annotations
            text = texts[0].description

            await ctx.send(f'Value detected :{text}')
        except Exception as err:
            await ctx.send(f'Error occured! {err}')

    @commands.group(name='ocrset')
    @commands.is_owner()
    async def ocrsettings(self, ctx: commands.Context):
        pass

    @ocrsettings.command(name='path')
    async def ocrset_path(self, ctx: commands.Context, path: Optional[str] = None):
        if path:
            await ctx.bot.set_shared_api_tokens("google_application_credentials", path=path)
            await ctx.send(f'service account file path set.')
        else:
            await ctx.bot.remove_shared_api_tokens("google_application_credentials", "path")
            await ctx.send(f'Removed path of service account file.')

