from typing import Literal, Optional
import json
import logging
import asyncio
import hashlib

from selenium import webdriver
from selenium.webdriver.remote.command import Command

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

        # bot.loop.create_task(self.initialize())

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

        await self.test_send("red is ready")

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

        await self.test_send("chrome options ready")

        log.debug("Initializing selenium...")

        try:
            self.driver = webdriver.Chrome(
                options=driver_options,
                desired_capabilities=driver_caps,
                executable_path=r"/home/qenv_dev/chromedriver",
            )
        except Exception as err:
            await self.test_send("Webdriver Error: {err}")

        await self.test_send("driver prepared")

        try:
            self.driver.get(
                "https://a90ur5.github.io/twBNS_F8ChattingChannel/web/index.html"
            )
        except Exception as err:
            await self.test_send("Driver get Error: {err}")
        
        await self.test_send(f"driver print: {self.driver}")
        # if self.driver:
        # self._sync = self.bot.loop.create_task(self.start_fetch())

    async def start_fetch(self):
        # await self.test_send("start")
        await self.bot.wait_until_red_ready()
        while self._enabled:
            # await self.test_send("twbnschat requesting...")
            await self.websocket_fetch()
            await asyncio.sleep(6.4)

    async def websocket_fetch(self):
        announce_queue = []
        log = self.driver.get_log("performance")

        if 10 < len(log) or len(log) <= 0:
            return

        output = False

        for wsData in log:

            try:
                wsJson = json.loads(wsData["message"])
                if (
                    wsJson["message"]["method"] == "Network.webSocketFrameReceived"
                    and wsJson["message"]["params"]["response"]["payloadData"][0] == "4"
                ):
                    wsParsed = json.loads(
                        wsJson["message"]["params"]["response"]["payloadData"][2:]
                    )
                    # await self.test_send(f"processed log: {wsParsed}")
                    if wsParsed[0] == "getStatus":
                        # await self.test_send("got status")
                        await self.config.accountA.set(wsParsed[1]["accountA"])
                        await self.config.accountB.set(wsParsed[1]["accountB"])
                        return
                    if wsParsed[0] == "getInquiry":
                        # await self.test_send("got inquiry")
                        announce_queue.append(wsParsed[1])
                        output = True
            except Exception:
                pass
        if output:
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

        data_l = [
            data
            for data in data_l
            if not self.in_cached(data["player"] + "|" + data["msg"])
        ]

        joinee = [
            f'`{data["time"]}`  **{data["player"]}**  `{data["msg"]}`'
            for data in data_l
        ]
        if len(joinee):
            for guild_id in guild_queue:
                try:
                    guild = self.bot.get_guild(guild_id)
                    channel = guild.get_channel(int(config[guild_id]["channel"]))
                    await channel.send("\n".join(joinee))
                except Exception:
                    pass

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
                self._cached_messages = self._cached_messages[
                    (30 - len(self._cached_messages)) :
                ]
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
                color=await ctx.embed_color(), title="TwB&S F8 chat settings"
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
            f"Channel for twbnschat has been {'unset' if channel is None else f'set at {channel.mention}'}."
        )

    @twbnschat.command(name="enabled")
    async def enabled(self, ctx: commands.Context, on_off: bool):
        """enables the channel for receiving

        Usage: [p]twbnschat enabled [on_off]
        """
        guild: discord.Guild = ctx.guild

        await self.config.guild(guild).toggle.set(on_off)

        if on_off and await self.config.guild(guild).channel() == None:
            await self.config.guild(guild).channel.set(ctx.channel.id)
            await ctx.send(
                f"Channel for twbnschat has been set to {ctx.channel.mention}."
            )

        await ctx.send(f"Twbnschat has been {'enabled' if on_off else f'disabled'}.")

    @twbnschat.command(name="alive")
    @commands.is_owner()
    async def alive(self, ctx: commands.Context):
        """(debug) function to check driver status"""
        try:
            self.driver.execute(Command.STATUS)
            await ctx.send("Driver is alive.")
        except Exception as err:
            await ctx.send(f"Driver is dead. Reason {err}")

    @twbnschat.command(name="refresh")
    @commands.is_owner()
    async def refresh(self, ctx: commands.Context):
        """refreshes selenium connection"""
        await self.bot.wait_until_red_ready()
        await ctx.send("Stopping twbnschat...")
        await self.stop(ctx)
        await asyncio.sleep(5)
        await self.start(ctx)
        await ctx.send("Done.")

    @twbnschat.command(name="stop")
    @commands.is_owner()
    async def stop(self, ctx: commands.Context):
        """stops selenium and executed loop"""
        self._enabled = False
        if self._sync:
            self._sync.cancel()
        try:
            self.driver.delete_all_cookies()
            self.driver.close()
            self.driver.quit()
        except Exception:
            pass
        await ctx.send(content="Twbnschat stopped.")

    @twbnschat.command(name="start")
    @commands.is_owner()
    async def start(self, ctx: commands.Context):
        """initialize selenium for chat fetching"""
        #  await self.config
        self.bot.loop.create_task(self.initialize())
        await self.alive(ctx)

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
