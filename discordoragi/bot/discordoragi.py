"""
Discord bot port of roboragi
"""
from discord.ext.commands import Bot
import yaml
from time import time
from aiohttp_wrapper import SessionManager
from ..helpers.discord_helpers import get_name_with_discriminator
from ..helpers import PostgresController
from logging import Formatter, INFO, StreamHandler, getLogger


class Discordoragi(Bot):
    """
    Discordoragi bot
    """
    def __init__(self):
        """
        Initializes the bot

        :param start_time: the time that the bot was created

        :param config: the now-converted config.yml file

        """
        self.start_time = int(time())
        with open("config/config.yml", 'r') as yml_config:
            config = yaml.load(yml_config)
        self.database_config = config['database_info']
        self.credentials = config['bot_credentials']
        self.footer = config['footer']
        self.logger = self.__get_logger()
        self.session_manager = SessionManager()
        super().__init__('?~')

    @classmethod
    async def get_bot(cls):
        bot_instance = cls()
        bot_instance.db_controller = await PostgresController.get_instance(
                bot_instance.logger,
                bot_instance.database_config)
        return bot_instance

    async def on_ready(self):
        self.logger.log(
            INFO,
            f'Logged in as {get_name_with_discriminator(self.user)}'
        )

    def start_bot(self, cogs):
        """
        actually start the bot

        :param cogs: cog extensions to be loaded
        """
        for cog in cogs:
            self.add_cog(cog)
        self.run(self.credentials['token'])

    def __get_logger(self):
        """
        returns a logger to be used

        :return: logger
        """
        logger = getLogger('discordoragi')
        console_handler = StreamHandler()
        console_handler.setFormatter(Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s')
        )
        logger.addHandler(console_handler)
        logger.setLevel(INFO)
        return logger
