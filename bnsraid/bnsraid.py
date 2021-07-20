from typing import Literal, Optional
import discord
from time import time
import asyncio
import re


import discord
from redbot.core import commands, checks
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

# correct
'''
http://g.bns.tw.ncsoft.com/ingame/api/training/characters/<CHARATER_NAME>/stat.json

http://g.bns.tw.ncsoft.com/ingame/bs/character/data/equipments?c=<CHARATER_NAME>

http://g.bns.tw.ncsoft.com/ingame/bs/character/data/abilities.json?c=<CHARATER_NAME>

http://g.bns.tw.ncsoft.com/ingame/bs/character/profile?c=<CHARATER_NAME>

http://g.bns.tw.ncsoft.com/ingame/bs/character/search/info?c=<CHARATER_NAME>

---
# 析唄
http://g.bns.tw.ncsoft.com/ingame/api/training/characters/析唄/stat.json
# returns json, current page, total page, and skill points

http://g.bns.tw.ncsoft.com/ingame/bs/character/data/equipments?c=析唄
# returns html of character info | weapon, gems, repair, all acc and names, clothes

http://g.bns.tw.ncsoft.com/ingame/bs/character/data/abilities.json?c=析唄
# returns huge json

http://g.bns.tw.ncsoft.com/ingame/bs/character/profile?c=析唄
# returns f2

http://g.bns.tw.ncsoft.com/ingame/bs/character/search/info?c=析唄
# character search UI

'''

class Bnsraid(commands.Cog):
    '''
    Bnsraid
    a utility cog to help bns guild raid setup
    '''

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=164900704526401545005,
            force_registration=True,
        )
        default_global = {
            'raids' : {},
            'emote' : '✅'
        }

        self.config.register_global(**default_global)

        self.raid_task = self.bot.loop.create_task(self._raid_handler())

    def cog_unload(self):
        self.raid_task.cancel()

    async def red_delete_data_for_user(
        self, *,
        requester: RequestType,
        user_id: int) -> None:
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @commands.guild_only()
    @commands.command(name='raid', aliases=['r'])
    @commands.bot_has_permissions(add_reactions=True, manage_messages=True)
    async def raid(
        self, ctx: commands.Context,
        *, content: str
        ):
        '''
            創建隊伍報名清單
            使用方式：[p]raid <副本名稱 | 其他描述>
            範例：[p]raid 4/20 破天 | 拓荒團 武器要求弒花9段 所有物品競標
        '''
        # await ctx.message.delete() # used to remove the command message


        content = content.split('\n')
        title = content[0]
        description = ''

        message = await ctx.send(f'由{ctx.author.display_name}發起')
        await message.add_reaction(await self.config.emote())

        try:
            description += '\n'.join(content[1:])
        except IndexError:
            pass

        async with self.config.raids() as raids:
            raids[str(message.id)] = {
                'msg' : [ctx.channel.id, message.id],
                'embed' : {
                    'title' : title,
                    'color' : ctx.author.color.value,
                    'description' : description,
                    'fields' : [
                        {
                            'name' : '參加人員：0',
                            'value' : '-'
                        }
                    ]
                },
                'signups' : {},
                'time' : time()
            }

        await self._embed_updater(message_id=str(message.id))

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        message_id = str(reaction.message.id)
        message_list = await self.config.raids()
        message_list = list(message_list.keys())
        if message_id not in message_list: return
        if user.id == self.bot.user.id: return

        emote = await self.config.emote()

        if reaction.emoji == emote:
            async with self.config.raids() as raids:
                raids[message_id]['signups'][str(user.id)] = str(user.display_name)
        await self._embed_updater(message_id=message_id)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        message_id = str(reaction.message.id)
        message_list = await self.config.raids()
        message_list = list(message_list.keys())
        if message_id not in message_list: return
        if user.id == self.bot.user.id: return

        emote = await self.config.emote()

        if reaction.emoji == emote:
            async with self.config.raids() as raids:
                try:
                    del raids[message_id]['signups'][str(user.id)]
                except Exception:
                    pass
        await self._embed_updater(message_id=message_id)

    async def _embed_updater(self, message_id: str, message=False):
        async with self.config.raids() as raids:
            channel = self.bot.get_channel(raids[message_id]['msg'][0])
            message = await channel.fetch_message(raids[message_id]['msg'][1])

            username = raids[message_id]['signups'].values()
            if len(username) != 0:
                username = '\n'.join([str(name) for name in username])
                raids[message_id]['embed']['fields'][0]['value'] = username
            else:
                raids[message_id]['embed']['fields'][0]['value'] = '-'
            raids[message_id]['embed']['fields'][0]['name'] = '參加人員：' + str(len(username))

            embed = discord.Embed.from_dict(raids[message_id]['embed'])
            await message.edit(embed = embed)

    async def _raid_delete(self, message_id: str):
        async with self.config.raids() as raids:
            del raids[message_id]
            channel = self.bot.get_channel(raids[message_id]['msg'][0])
            message = await channel.fetch_message(raids[message_id]['msg'][1])
            try:
                await message.delete()
            except Exception:
                pass

    async def _raid_timer(self, message_id: str):
        thirtyDays = 86400*30
        raids = await self.config.raids()
        remain = thirtyDays - (time() - raids[message_id]['time'])
        if remain > 0:
            await asyncio.sleep(int(remain))
        await self._raid_delete(message_id)

    async def _raid_handler(self):
        await self.bot.wait_until_red_ready()
        try:
            _raid_coros = []
            raids = await self.config.raids()
            for message_id in raids:
                _raid_coros.append(self._raid_timer(message_id))
            await asyncio.gather(*_raid_coros)
        except Exception:
            pass

    @commands.group(name='devbnsraid')
    @checks.admin_or_permissions()
    async def commands_devraid(self, ctx: commands.Context):
        pass

    @commands_devraid.command(name='show')
    @checks.is_owner()
    async def devbnsraid_showall(self, ctx: commands.Context):
        async with self.config.raids() as raids:
            await ctx.send(raids)

    @commands_devraid.command(name='remove')
    async def devbnsraid_remove(self, ctx: commands.Context, message_id: str):
        message_list = await self.config.raids()
        message_list = list(message_list.keys())
        if message_id in message_list:
            await self._raid_delete(message_id)
            await ctx.tick()

    @commands_devraid.command(name='remall')
    async def devbnsraid_remall(self, ctx: commands.Context):
        message_list = await self.config.raids()
        message_list = list(message_list.keys())
        for message_id in message_list:
            await self._raid_delete(message_id)
        await ctx.tick()
