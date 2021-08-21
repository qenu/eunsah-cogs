import twbnschat
from typing import Literal, Optional
import json
import logging
import asyncio

from selenium import webdriver
from chromedriver_py import binary_path


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
        self._enabled = True
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

        default_global = {
            # "accountA": None,
            # "accountB": None,
            # "timestamp" : None,
            "url": "",
        }

        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

        # self.bot.loop.create_task(self.initialize())
        self.initialize()

    async def red_delete_data_for_user(
        self, *, requester: RequestType, user_id: int
    ) -> None:
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    def cog_unload(self):
        log.debug("Unloading twBNSchat...")
        self._enabled = False
        if self._sync:
            self._sync.cancel()
        self.driver.quit()
        log.debug("Stopped selenium.")
        log.debug("twBNSchat unloaded.")

    def initialize(self):

        driver_options = webdriver.ChromeOptions()
        driver_options.add_argument("--mute-audio")
        driver_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        driver_options.add_argument("start-maximized")
        driver_options.add_argument("disable-infobars")
        driver_options.add_argument("--disable-extensions")
        driver_options.add_argument("--disable-gpu")
        driver_options.add_argument("--disable-dev-shm-usage")
        driver_options.add_argument("--no-sandbox")
        driver_options.headless = True

        driver_caps = webdriver.DesiredCapabilities.CHROME.copy()
        driver_caps["goog:loggingPrefs"] = {"performance": "ALL"}

        log.debug("Initializing selenium...")
        self.driver = webdriver.Chrome(
            options=driver_options,
            desired_capabilities=driver_caps,
            executable_path=r"/usr/bin/chromedriver",
        )
        self.driver.get('https://a90ur5.github.io/twBNS_F8ChattingChannel/web/index.html')
        self._sync = self.bot.loop.create_task(self.start_fetch())

    async def start_fetch(self):
        await self.bot.wait_until_red_ready()
        while self._enabled:
            await self.websocket_fetch()
            await asyncio.sleep(3)

    async def websocket_fetch(self):
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
        # await self.test_send("channel announce")

        config = await self.config.all_guilds()
        guild_queue = [
            guild_id for guild_id in config if config[guild_id]["toggle"] is True
        ]
        await self.test_send(guild_queue)
        if not len(guild_queue):
            return
        await self.test_send("making embed")
        embed = discord.Embed(title=data["player"], description=data["msg"])
        embed.set_footer(text=data["time"])
        await self.test_send("read to send embed")

        for guild_id in guild_queue:
            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel(int(config[guild_id]["channel"]))
            await channel.send(embed=embed)

    @commands.group(name="twbnschat")
    @commands.admin_or_permissions(manage_guild=True)
    async def twbnschat(self, ctx):
        """settings for twbnschat"""
        await ctx.trigger_typing()
        await self.test_send('maybe>')
        if ctx.invoked_subcommand is None:
            guild: discord.Guild = ctx.guild
            config = await self.config.guild(guild).all()

            embed = discord.Embed(
                color=await ctx.embed_color(), title="Current StreamRole Settings"
            )
            embed.add_field(name="Enabled", value=config["toggle"])

            embed.add_field(
                name="Channel",
                value=ctx.guild.get_channel(config["channel"]).mention,
            )

            await ctx.send(embed=embed)

    @twbnschat.command(name="channel")
    async def channel(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ):
        """sets the channel to receive driver updates

        Usage: [p]twbnschat channel <#channl_mention>
        leave blank to unset
        """
        await self.config.guild(ctx.guild).channel.set(
            None if channel is None else channel.id
        )
        if channel is None:
            await self.enabled(ctx, False)
        await ctx.send(
            f"channel for twbnschat has been {'unset' if channel is None else f'set at {channel.mention}'}."
        )

    @twbnschat.command(name="enabled")
    async def enabled(self, ctx: commands.Context, boo: bool):
        """enables the channel for receiving

        Usage: [p]twbnschat enabled [True | False]
        """
        guild: discord.Guild = ctx.guild

        await self.config.guild(guild).toggle.set(boo)

        if boo and await self.config.guild(guild).channel() == None:
            await self.config.guild(guild).channel.set(ctx.channel.id)
            await ctx.send(
                f"channel for twbnschat has been set to {ctx.channel.mention}"
            )

        await ctx.send(f"twbnschat has been {'enabled' if boo else f'disabled'}.")

    async def test_send(self, item):
        g = self.bot.get_guild(247820107760402434)
        c = g.get_channel(879630016856596521)
        await c.send(content=str(item))
