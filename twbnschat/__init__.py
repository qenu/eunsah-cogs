import json
from pathlib import Path

from redbot.core.bot import Red
from .twbnschat import twBNSchat


async def setup(bot: Red) -> None:
    bot.add_cog(twBNSchat(bot))
