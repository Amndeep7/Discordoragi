"""
Actually runs the code
"""
from bot import Discordoragi
from cogs import Search
import asyncio


async def run(future):
    bot = await Discordoragi.get_bot()
    search_cog = await Search.create_search(bot)
    cogs = [
      search_cog
    ]
    future.set_result({'bot': bot, 'cogs': cogs})

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    future = asyncio.Future()
    loop.run_until_complete(run(future))
    bot = future.result()['bot']
    cogs = future.result()['cogs']

    bot.start_bot(cogs)
