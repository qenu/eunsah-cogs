import functools
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
        # self._status = ('-', '-')
        self._cached_messages = []

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
            "accountA": None,
            "accountB": None,
            # "timestamp" : None,
            # "url": "",
        }

        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

        bot.loop.create_task(self.initialize())

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

    async def initialize(self):
        await self.bot.wait_until_red_ready()

        driver_options = webdriver.ChromeOptions()
        driver_options.add_argument("--mute-audio")
        driver_options.add_experimental_option("excludeSwitches", ["enable-logging"])
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
        await self.test_send("start")
        await self.bot.wait_until_red_ready()
        while self._enabled:
            await self.test_send("in loop")
            await self.websocket_fetch()
            await asyncio.sleep(8)

    async def websocket_fetch(self):
        announce_queue = []
        log = self.driver.get_log("performance")

        if 30 < len(log) or len(log) <= 0:
            return
        await self.test_send(f"got log, len: {len(log)}")

        output = False

        for wsData in log:
            await self.test_send(str(wsData))
            try:
                wsJson = json.loads(wsData["message"])
                if (
                    wsJson["message"]["method"] == "Network.webSocketFrameReceived"
                    and wsJson["message"]["params"]["response"]["payloadData"][0] == "4"
                ):
                    await self.test_send(f"start processing")

                    wsParsed = json.loads(
                        wsJson["message"]["params"]["response"]["payloadData"][2:]
                    )
                    await self.test_send(f"processed log: {wsParsed}")
                    if wsParsed[0] == "getStatus":
                        await self.test_send("status")
                        await self.config.accountA.set(wsParsed[1]["accountA"])
                        await self.config.accountB.set(wsParsed[1]["accountB"])
                        return
                    if wsParsed[0] == "getInquiry":
                        await self.test_send("inquiry")
                        announce_queue.append(wsParsed[1])
                        output = True
            except Exception:
                pass
        if output:
            # for relay in announce_queue:
            #     await self.test_send("relay")

            #     await self.channel_announce(relay)
            await self.test_send("text")
            await self.text_announce(announce_queue)

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
            try:
                guild = self.bot.get_guild(guild_id)
                channel = guild.get_channel(int(config[guild_id]["channel"]))
                await channel.send(embed=embed)
            except Exception:
                pass

    async def text_announce(self, data_l: list):

        config = await self.config.all_guilds()

        guild_queue = [
            guild_id for guild_id in config if config[guild_id]["toggle"] is True
        ]
        if not len(guild_queue):
            return

        data_l = [data for data in data_l if not self.in_cached(data["player"] + "|" + data["msg"])]

        joinee = [f'{data["time"]} **{data["player"]}** `{data["msg"]}`' for data in data_l]

        await self.test_send("\n".join(joinee))

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
            if len(self._cached_messages) >= 30:
                self._cached_messages = self._cached_messages[:30]
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
        await ctx.send(content=self.driver.current_url)

    @twbnschat.command(name="refresh")
    @commands.is_owner()
    async def refresh(self, ctx: commands.Context):
        """refreshes selenium connection"""
        await ctx.send("refresing selenium connection")
        self._enabled = False
        if self._sync:
            self._sync.cancel()
        try:
            self.driver.delete_all_cookies()
            self.driver.close()
            self.driver.quit()
        except Exception:
            pass

        await asyncio.sleep(3)

        await ctx.send("re-initializing driver")

        # foo = functools.partial(self.initialize)
        # task = self.bot.loop.run_in_executor(None, foo)
        # try:
        #     await asyncio.wait_for(task, timeout=60)
        # except asyncio.TimeoutError:
        #     await ctx.send("initialization timeout")
        #     return
        await self.initialize()
        await ctx.send("done")

    @twbnschat.command(name="url")
    @commands.is_owner()
    async def url(self, ctx: commands.Context, url: Optional[str] = None):
        await self.config

    @twbnschat.command(name="status")
    async def status(self, ctx: commands.Context):
        """shows the last obtained status from site"""
        emb = discord.Embed(description="Last Reported")
        emb.add_field(name="accountA", value=await self.config.accountA())
        emb.add_field(name="accountB", value=await self.config.accountB())

        await ctx.send(embed=emb)

    async def test_send(self, text: str):
        g = self.bot.get_guild(247820107760402434)
        c = g.get_channel(879630016856596521)
        await c.send(content=text)
