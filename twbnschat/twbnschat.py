import twbnschat
from typing import Literal, Optional
import json
import logging
import asyncio
import hashlib

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
        self._enabled = True
        self._cached_messages = list()

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
        #     "url": "",
        # }

        self.config.register_guild(**default_guild)
        # self.config.register_global(**default_global)

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
        self.driver.get(
            "https://a90ur5.github.io/twBNS_F8ChattingChannel/web/index.html"
        )
        self._sync = self.bot.loop.create_task(self.start_fetch())

    async def start_fetch(self):
        await self.bot.wait_until_red_ready()
        while self._enabled:
            await self.websocket_fetch()
            await asyncio.sleep(1.5)

    async def websocket_fetch(self):
        announce_queue = list()
        for wsData in self.driver.get_log("performance"):
            wsJson = json.loads(wsData["message"])
            await self.test_send(wsJson["message"]["params"]["response"]["payloadData"])
            if (
                wsJson["message"]["method"] == "Network.webSocketFrameReceived"
                and wsJson["message"]["params"]["response"]["payloadData"][:2] == "42"
            ):
                wsParsed = json.loads(
                    wsJson["message"]["params"]["response"]["payloadData"][2:]
                )
                # if wsParsed[0] == 'getStatus':
                if wsParsed[0] == "getInquiry":
                    announce_queue.append(wsParsed[1])

        for relay in announce_queue:
            await self.channel_announce(relay)

    async def channel_announce(self, data: dict):
        config = await self.config.all_guilds()
        guild_queue = [
            guild_id for guild_id in config if config[guild_id]["toggle"] is True
        ]
        if not len(guild_queue):
            return

        if self.in_cached(data["player"] + "|" + data["msg"]):
            return

        embed = discord.Embed(
            title=data["player"],
            description=data["msg"],
            color=self.string2discordColor(data["player"]),
        )
        embed.set_footer(text=data["time"])
        for guild_id in guild_queue:
            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel(int(config[guild_id]["channel"]))
            await channel.send(embed=embed)

    def string2discordColor(self, text: str) -> str:
        hashed = str(
            int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) % (10 ** 9)
        )
        r = int(hashed[:3]) % 255
        g = int(hashed[3:6]) % 255
        b = int(hashed[6:]) % 255

        return discord.Color.from_rgb(r, g, b)

    def in_cached(self, text: str) -> bool:
        if text in self._cached_messages:
            return True
        else:
            self._cached_messages.append(text)
            while len(self._cached_messages) >= 30:
                self._cached_messages.pop(0)
            return False

    @commands.group(name="twbnschat")
    @commands.admin_or_permissions(manage_guild=True)
    async def twbnschat(self, ctx):
        """settings for twbnschat"""
        await ctx.trigger_typing()
        if ctx.invoked_subcommand is None:
            guild: discord.Guild = ctx.guild
            config = await self.config.guild(guild).all()

            embed = discord.Embed(
                color=await ctx.embed_color(), title="twB&S F8 chat settings"
            )
            embed.add_field(name="Enabled", value=config["toggle"])

            channel = (
                ctx.guild.get_channel(config["channel"]).mention
                if ctx.guild.get_channel(config["channel"])
                else "None"
            )

            embed.add_field(
                name="Channel",
                value=channel,
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

    @twbnschat.command(name="checkcache")
    @commands.is_owner()
    async def checkcache(self, ctx: commands.Context):
        """(debug) function used to view cached messages"""
        await ctx.send(content=self._cached_messages)

    async def test_send(self, text:str):
        g = self.bot.get_guild(247820107760402434)
        c = g.get_channel(879630016856596521)
        await c.send(content= text)