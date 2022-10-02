"""
Actually runs the code
"""
from .bot import Discordoragi
from .cogs import Search
from asyncio import get_event_loop


def run():
    loop = get_event_loop()
    bot = loop.run_until_complete(Discordoragi.get_bot())
    search_cog = loop.run_until_complete(Search.create_search(bot))
    cogs = [
      search_cog
    ]
    bot.start_bot(cogs)


if __name__ == '__main__':
    run()
