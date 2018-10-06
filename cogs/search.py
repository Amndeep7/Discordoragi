"""
A cog that handles searching for anime/manga/ln found
in brackets.
"""
from enum import Enum
from discord import Embed
from minoshiro import Medium, Minoshiro, Site
import datetime
import re


class Replace(Enum):
    MAL = 1
    AL = 2
    AP = 3
    ANIDB = 4
    KITSU = 5
    MU = 6
    LNDB = 7
    NU = 8
    VNDB = 9


def cleanup_description(desc) -> str:
    for match in re.finditer(r"([\[\<\(](.*?)[\]\>\)])", desc, re.S):
        if 'ource' in match.group(1).lower():
            desc = desc.replace(match.group(1), '')
        if 'MAL' in match.group(1):
            desc = desc.replace(match.group(1), '')

    for match in re.finditer(r"([\<](.*?)[\>])", desc, re.S):
        if 'br' in match.group(1).lower():
            desc = desc.replace(match.group(1), ' ')
    return desc


def clean_message(message) -> str:
    """
    Returns a message, but stripped of all code markup and emojis
    Uses regex to parse
    :param message: a message string
    :returns: message string - code markup and emojis
    """
    no_multi_codeblocks = re.sub(
        r"^`{3}([\S]+)?\n([\s\S]+)\n`{3}", "", message.clean_content)
    no_single_codeblocks = re.sub(r"\`(.*\s?)\`", "", no_multi_codeblocks)
    no_emojis = re.sub(r'<:.+?:([0-9]{15,21})>', "", no_single_codeblocks)
    return no_emojis


def get_all_searches(message, expanded_allowed):
    matches = 0
    for match in re.finditer(
            r"\{{2}([^}]*)\}{2}|\<{2}([^>]*)\>{2}|\]{2}([^]]*)\[{2}",
            message, re.S):
        matches += 1
        if matches > 1:
            expanded_allowed = False
        if '<<' in match.group(0):
            cleaned_search = re.sub(r"\<{2}|\>{2}", "", match.group(0))
            yield {
                'medium':  Medium.MANGA,
                'search': cleaned_search,
                'expanded': expanded_allowed}
        if '{{' in match.group(0):
            cleaned_search = re.sub(r"\{{2}|\}{2}", "", match.group(0))
            yield {
                'medium': Medium.ANIME,
                'search': cleaned_search,
                'expanded': expanded_allowed}
        if ']]' in match.group(0):
            cleaned_search = re.sub(r"\]{2}|\[{2}", "", match.group(0))
            yield {
                'medium': Medium.LN,
                'search': cleaned_search,
                'expanded': expanded_allowed}

        message = re.sub(re.escape(match.group(0)), "", message)

    for match in re.finditer(r"\{([^{}]*)\}|\<([^<>]*)\>|\]([^[\]]*)\[",
                             message, re.S):
        if '<' in match.group(0):
            cleaned_search = re.sub(r"\<|\>", "", match.group(0))
            yield {
                'medium': Medium.MANGA,
                'search': cleaned_search,
                'expanded': False}
        if '{' in match.group(0):
            cleaned_search = re.sub(r"\{|\}", "", match.group(0))
            yield {
                'medium': Medium.ANIME,
                'search': cleaned_search,
                'expanded': False}
        if ']' in match.group(0):
            cleaned_search = re.sub(r"\]|\[", "", match.group(0))
            yield {
                'medium': Medium.LN,
                'search': cleaned_search,
                'expanded': False}
    return


def get_response_dict(entry_info, medium):
    assert (Site.ANILIST in entry_info.keys()),\
        "Entry must have either mal or anilist responses"
    resp_dict = {}
    resp_dict['info'] = {}
    url_string = ''
    genre_string = ''
    if medium == Medium.LN:
        medium = Medium.MANGA
    entry_info[Site.MAL] = {'url': None}
    entry_info[Site.MAL]['url'] =\
        f'https://myanimelist.net/{medium.name.lower()}/'\
        f'{entry_info[Site.ANILIST]["idMal"]}'
    resp_dict['title'] = entry_info[Site.ANILIST]['title']['romaji']
    resp_dict['kana'] = entry_info[Site.ANILIST]['title']['native']
    resp_dict['synopsis'] = cleanup_description(
        entry_info[Site.ANILIST]['description'])
    for key in entry_info.keys():
        if entry_info[key]['url']:
            url_string += f'[{Replace(key.value).name}]'\
                          f'({entry_info[key]["url"]}), '
    resp_dict['links'] = url_string.strip(', ')
    if entry_info[Site.ANILIST] and entry_info[Site.ANILIST]['genres']:
        for genre in entry_info[Site.ANILIST]['genres']:
            genre_string += f'{genre}, '
        resp_dict['info']['genres'] = genre_string.rstrip(', ')
    resp_dict['info']['status'] = entry_info[Site.ANILIST]['status'].title()
    resp_dict['image'] = entry_info[Site.ANILIST]['coverImage']['medium']
    if medium == Medium.ANIME:
        resp_dict['info']['episodes'] = entry_info[Site.ANILIST]['episodes']
        temp_date = datetime.datetime.now() + datetime.timedelta(
            seconds=entry_info[Site.ANILIST]['nextAiringEpisode']['timeUntilAiring']) \
            if entry_info[Site.ANILIST] and \
            not entry_info[Site.ANILIST]['status'] == 'FINISHED' else None
        if temp_date:
            time_diff = temp_date - datetime.datetime.now()
            resp_dict['info']['next episode'] = \
                f'{time_diff.days} days {time_diff.seconds//3600} hours'
    else:
        resp_dict['info']['chapters'] = entry_info[Site.ANILIST]['chapters']
        resp_dict['info']['volumes'] = entry_info[Site.ANILIST]['volumes']
    return resp_dict


class Search:

    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.footer_title = ''
        for x in range(0, 59):
            self.footer_title += '\_'
        self.footer = bot.footer

    @classmethod
    async def create_search(cls, bot):
        search = cls(bot)
        search.mino = await Minoshiro.from_postgres(
            search.bot.database_config
        )
        return search

    async def on_message(self, message):
        if message.author.bot:
            return
        string = r"{]<"
        if not any(elem in message.clean_content for elem in string):
            return
        cleaned_message = await self.__execute_commands(
                message)
        entry_info = {}
        for thing in get_all_searches(cleaned_message, True):
            async with message.channel.typing():
                self.logger.info(f'Searching for {thing["search"]}')
                try:
                    async for data in self.mino.yield_data(
                            thing['search'],
                            thing['medium'],
                            sites=[Site.ANILIST]):
                        entry_info[data[0]] = data[1]
                except Exception as e:
                    self.logger.warning(
                        f'Error searching for {thing["search"]}: {e}')
                try:
                    resp = get_response_dict(entry_info, thing['medium'])
                except AssertionError:
                    await message.add_reaction('\N{Cross Mark}')
                    continue
                embed = self.__build_entry_embed(resp, thing['expanded'])
                info_message = None
                if embed is not None:
                    self.logger.info('Found entry, creating message')
                    info_message = await message.channel.send(embed=embed)
                else:
                    await message.add_reaction('\N{Cross Mark}')
                if not info_message:
                    await message.add_reaction('\N{Cross Mark}')
                    return
                try:
                    if thing['medium'] == Medium.ANIME:
                        local_sites = [Site.KITSU, Site.ANIDB]
                    elif thing['medium'] == Medium.VN:
                        return
                    elif thing['medium'] == Medium.LN:
                        local_sites = \
                            [Site.NOVELUPDATES, Site.LNDB, Site.KITSU]
                    else:
                        local_sites = [Site.MANGAUPDATES, Site.KITSU]
                    async for data in self.mino.yield_data(
                            resp['title'], thing['medium'], sites=local_sites):
                        entry_info[data[0]] = data[1]
                    temp_embed = info_message.embeds[0]
                    temp_desc = temp_embed.description
                    url_string = ''
                    for key in entry_info.keys():
                        if entry_info[key]['url']:
                            url_string += f'[{Replace(key.value).name}]'\
                                        f'({entry_info[key]["url"]}), '
                    temp_desc = url_string.strip(', ')
                    temp_embed.description = temp_desc
                    await info_message.edit(embed=temp_embed)
                except Exception as e:
                    self.logger.warning(
                        f'Error searching for {thing["search"]}: '
                        f'{e}')
                    await message.add_reaction('\N{Cross Mark}')
                return await self.bot.db_controller.add_request({
                    'requester_id': message.author.id,
                    'message_id': info_message.id,
                    'server_id': message.channel.guild.id,
                    'medium': thing['medium'],
                    'title': resp['title']
                })

    async def __execute_commands(self, message):
        cleaned_message = clean_message(message)
        for match in re.finditer(r"\{([^{}]*)\}|\<([^<>]*)\>|\]([^[\]]*)\[",
                                 cleaned_message, re.S):
            command = re.sub(r'[<>{}[\]]', '', match.group(0))
            if command.startswith('!'):
                if command.lower() == '!toggle expanded':
                    pass
                if command.lower() == '!help':
                    await message.channel.send(embed=self.__print_help_embed())
                if command.lower() == '!sstats':
                    await message.channel.send(
                        embed=await self.__print_server_stats(
                            message.channel.guild))
                if command.lower().startswith('!stats'):
                    if message.mentions:
                        await message.channel.send(
                            embed=await self.__print_user_stats(
                                message.mentions[0]))
                    else:
                        await message.channel.send(
                            embed=Embed(
                                title=f'Command Error :x:',
                                description=f'General stats are disabled for '
                                            f'now, mention someone to see '
                                            f'individual stats'
                            ),
                            delete_after=3
                        )
                cleaned_message = re.sub(
                    re.escape(match.group(0)), "", cleaned_message)
        return cleaned_message

    async def __print_user_stats(self, user):
        try:
            user_stats = await self.bot.db_controller.get_user_stats(user.id)
            percentage = \
                user_stats['user_requests']/user_stats['global_requests']
            stats_str = f'__*Some usage stats for {user.mention}*__:\n'
            stats_str += f'\n**{user_stats["user_requests"]}** requests made '\
                         f'({percentage * 100}% of all requests and '\
                         f'#{user_stats["rank"]} overall)\n'
            stats_str += f'**{user_stats["unique_requests"]}** '\
                         f'unique anime/manga/ln/vn requests made\n\n'
            stats_str += \
                f'**{user.name}\'s most frequently requested items:**\n\n'
            count = 1
            for item in user_stats['top_requests']:
                stats_str += f'{count}. **{item["title"]}**'\
                             f' ({Medium(item["medium"]).name.title()} - '\
                             f'{item["count"]} requests)\n'
                count += 1
            embed = Embed(
                title=f"{user.name}'s Stats",
                description=stats_str
            )
            embed.add_field(
                name=self.footer_title,
                value=self.footer
            )
            return embed
        except Exception as e:
            self.logger.warning(f'Error getting user stats: {e}')

    async def __print_server_stats(self, server):
        try:
            server_stats = await \
                self.bot.db_controller.get_server_stats(server.id)
            percentage = \
                server_stats['server_requests']/server_stats['global_requests']
            stats_str = f'__*Some usage stats for {server.name}*__:\n'
            stats_str += f'\n**{server_stats["server_requests"]}** requests '\
                         f'made ({percentage * 100}% of all requests and '\
                         f'#{server_stats["rank"]} overall)\n'
            stats_str += f'**{server_stats["unique_requests"]}** '\
                         f'unique anime/manga/ln/vn requests made\n\n'
            stats_str += \
                f'**{server.name}\'s most frequently requested items:**\n\n'
            count = 1
            for item in server_stats['top_requests']:
                stats_str += f'{count}. **{item["title"]}**'\
                             f' ({Medium(item["medium"]).name.title()} - '\
                             f'{item["count"]} requests)\n'
                count += 1
            embed = Embed(
                title=f"{server.name}'s Stats",
                description=stats_str
            )
            embed.add_field(
                name=self.footer_title,
                value=self.footer
            )
            return embed
        except Exception as e:
            self.logger.warning(f'Error getting server stats: {e}')

    def __print_help_embed(self):
        try:
            embed_title = "__Help__"
            help_info = \
                'You can call the bot by using specific tags on one of the '\
                'active servers.\n\nAnime can be called using {curly braces},'\
                ' manga can be called using <arrows> and light novels can be'\
                ' called using reverse ]square braces[ (e.g.{Nisekoi} or '\
                '<Bonnouji> or ]Utsuro no Hako to Zero no Maria\[).\n\n'\
                '{Single} will give you a normal set of information while'\
                ' {{double}} will give you expanded information. '\
                'Examples of these requests can be found [here]'\
                '(https://github.com/dashwav/Discordoragi/wiki/Example-Output)'
            embed = Embed(
                title=embed_title,
                description=help_info
            )
            embed.add_field(
                name=self.footer_title,
                value=self.footer
            )
            return embed
        except Exception as e:
            self.logger.warning(f'Exception occured when printing help: {e}')

    def __build_entry_embed(self, entry_info, is_expanded):
        info_text = f'{entry_info["kana"]}\n\n('
        for key, data in entry_info['info'].items():
            if not data:
                continue
            info_text += f'**{key.title()}**: {data} | '
        info_text = info_text.rstrip(' | ') + ')'

        try:
            embed = Embed(
                title=entry_info['title'],
                description=entry_info['links'],
                type='rich'
            )
            embed.set_thumbnail(url=entry_info['image'])
            embed.add_field(
                name='__Info__',
                value=info_text
            )
            if is_expanded:
                if len(entry_info['synopsis'].rstrip()) > 1023:
                    desc_text = entry_info['synopsis'].rstrip()[:1020] + '...'
                else:
                    desc_text = entry_info['synopsis'].rstrip()
                embed.add_field(
                    name='__Description__',
                    value=desc_text
                )
            embed.add_field(
                name=self.footer_title,
                value=self.footer
            )
            return embed
        except Exception as e:
            self.logger.warning(f'Error creating embed: {e}')
