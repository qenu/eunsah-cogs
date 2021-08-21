from typing import Literal, Optional
import json
import logging
import asyncio

from selenium import webdriver

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]
log = logging.getLogger("red.eunsah-cogs.twBNSchat")


class twBNSchat(commands.Cog):
    """
    Fetch Taiwan Blade&Soul f8 chat
    ---
    For any issues about this cog
    Contact me via ba#0373
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self._sync = False
        # self.bot.loop.create_task(self.initialize())

        self.config = Config.get_conf(
            self,
            identifier=164900704526401545021,
            force_registration=True,
        )

        default_guild = {
            "channel": None,
            "toggle": False,
        }

        # default_global = {
        #     "accountA": None,
        #     "accountB": None,
        #     "timestamp" : None,
        # }

        self.config.register_guild(**default_guild)
        # self.config.register_global(**default_global)

    async def red_delete_data_for_user(
        self, *, requester: RequestType, user_id: int
    ) -> None:
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    def cog_unload(self):
        log.debug("Unloading twBNSchat...")
        if self._sync:
            self._sync.cancel()
        self.exit_driver()
        log.debug("Stopped selenium.")
        log.debug("twBNSchat unloaded.")

    async def initialize(self):
        driver_options = webdriver.ChromeOptions()
        driver_options.add_argument("--mute-audio")
        driver_options.add_argument("--window-size=400,600")
        driver_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        driver_options.headless = True

        driver_caps = webdriver.DesiredCapabilities.CHROME.copy()
        driver_caps["goog:loggingPrefs"] = {"performance": "ALL"}

        log.debug("Initializing selenium...")
        self.driver = webdriver.Chrome(
            options=driver_options, desired_capabilities=driver_caps
        )
        self._sync = self.bot.loop.create_task(self.websocket_fetch)

    async def exit_driver(self):
        self._sync.cancel()
        self.driver.quit()

    async def websocket_fetch(self):
        await asyncio.sleep(2.5)
        for wsData in self.driver.get_log("performance"):
            wsJson = json.loads(wsData["message"])
            if (
                wsJson["message"]["method"] == "Network.webSocketFrameReceived"
                and wsJson["message"]["params"]["response"]["payloadData"][:2] == "42"
            ):
                wsParsed = json.loads(
                    wsJson["message"]["params"]["response"]["payloadData"][2:]
                )
                # if wsParsed[0] == 'getStatus':
                if wsParsed[0] == "getInquiry":
                    await self.channel_announce(wsParsed[1])

    async def channel_announce(self, data: dict):
        config = self.config.all_guilds()
        guild_queue = [
            guild_id for guild_id in config if config[guild_id]["channel"] is not None
        ]
        if not len(guild_queue):
            return
        embed = discord.Embed(title=data["player"], description=data["msg"])
        embed.set_footer(text=data["time"])
        for guild_id in guild_queue:
            guild = await self.bot.get_guild(guild_id)
            channel = await guild.get_channel(int(config[guild_id]["channel"]))
            await channel.send()

    @commands.group(name="f8chat")
    @commands.admin_or_permissions(manage_guild=True)
    async def f8chat(self, ctx):
        pass

    @f8chat.command(name="channel")
    async def channel(self, ctx: commands.Context, channel: Optional[discord.Channel] = None):
        '''sets the channel to announce updates

        Usage: [p]bnsf8chat channel <#channl_mention>
        leave blank to unset
        '''
        await self.config.guild(ctx.guild).channel.set(None if channel is None else channel.id)
        await ctx.send(f"f8chat has been {'disabled' if channel is None else f'enabled at {channel.mention}'}")

    @f8chat.command(name="toggle")
    @commands.is_owner()
    async def toggle(self, ctx: commands.Context):
        self.bot.loop.create_task(self.initialize())
        log.debug("f8chat has started...")


