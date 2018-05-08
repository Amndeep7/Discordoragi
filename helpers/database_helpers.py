from asyncpg import InterfaceError, create_pool
from asyncpg.pool import Pool


async def make_tables(pool: Pool, schema: str):
        """
        Make tables if they don't exist.
        :param pool: the connection pool.
        :param schema: the schema name.
        """
        await pool.execute('CREATE SCHEMA IF NOT EXISTS {};'.format(schema))

        servers = """
        CREATE TABLE IF NOT EXISTS {}.servers (
        server INT,
        expanded BOOLEAN,
        stats BOOLEAN,
        PRIMARY KEY (server)
        );""".format(schema)

        requests = """
        CREATE TABLE IF NOT EXISTS {}.requests (
        id SERIAL,
        message BIGINT,
        requester BIGINT,
        server BIGINT,
        medium SMALLINT,
        title VARCHAR NOT NULL,
        PRIMARY KEY (id, requester, server)
        );
        """.format(schema)

        await pool.execute(servers)
        await pool.execute(requests)


class PostgresController():
    """
    To be able to integrate with an existing database, all tables for
    discordoragi will be put under the `discordoragi` schema unless a
    different schema name is passed to the __init__ method.
    """
    __slots__ = ('pool', 'schema', 'logger')

    def __init__(self, pool: Pool, logger, schema: str = 'discordoragi'):
        """
        Init method. Create the instance with the `get_instance` method to make
        sure you have all the tables needed.
        :param pool: the `asyncpg` connection pool.
        :param logger: logger object used for logging.
        :param schema: the schema name, default is `discordoragi`
        """
        self.pool = pool
        self.schema = schema
        self.logger = logger

    @classmethod
    async def get_instance(cls, logger, connect_kwargs: dict = None,
                           pool: Pool = None, schema: str = 'discordoragi'):
        """
        Get a new instance of `PostgresController`
        This method will create the appropriate tables needed.
        :param logger: the logger object.
        :param connect_kwargs:
            Keyword arguments for the
            :func:`asyncpg.connection.connect` function.
        :param pool: an existing connection pool.
        One of `pool` or `connect_kwargs` must not be None.
        :param schema: the schema name used. Defaults to `discordoragi`
        :return: a new instance of `PostgresController`
        """
        assert connect_kwargs or pool, (
            'Please either provide a connection pool or '
            'a dict of connection data for creating a new '
            'connection pool.'
        )
        if not pool:
            try:
                pool = await create_pool(**connect_kwargs)
                logger.info('Connection pool made.')
            except InterfaceError as e:
                logger.error(str(e))
                raise e
        logger.info('Creating tables...')
        await make_tables(pool, schema)
        logger.info('Tables created.')
        return cls(pool, logger, schema)

    async def add_request(self, request):
        """
        Adds a request to the database
        :param request: a dict containing the info to put
            into the database
        """
        sql = """
        INSERT INTO {}.requests (requester, message, server, medium, title)
        VALUES ($1, $2, $3, $4, $5);
        """.format(self.schema)
        try:
            await self.pool.execute(sql,
                                    request['requester_id'],
                                    request['message_id'],
                                    request['server_id'],
                                    request['medium'].value,
                                    request['title'])
        except Exception as e:
            self.logger.warning(
                f'Exception occured white adding request: {e}')

    async def add_server(self, server_id):
        """
        Adds a request to the database
        :param server_id: ID of the server to put into the database
        """
        sql = """
        INSERT INTO {}.servers (server)
        VALUES ($1) ON CONFLICT DO NOTHING;
        """.format(self.schema)
        try:
            await self.pool.execute(sql, server_id)
        except Exception as e:
            self.logger.warning(f'Exception occured while adding server: {e}')

    async def toggle_server_setting(self, server_id, setting):
        """
        Toggles one of the server settings
        :param setting: either 'stats' or 'expanded'
        """
        sql = """
        UPDATE {}.servers
        SET ($1) = NOT ($1)
        WHERE server = ($2);
        """.format(self.schema)
        try:
            await self.pool.execute(sql, setting, server_id)
        except Exception as e:
            self.logger.warning(f'Exception occured while adding server: {e}')

    async def __global_requests(self):
        sql = """
        SELECT count(*) from {}.requests;
        """.format(self.schema)
        try:
            count = await self.pool.fetchval(sql)
            return int(count)
        except Exception as e:
            self.logger.warning(
                f'Exception occured while getting total requests: {e}')

    async def get_server_setting(self, server_id, setting) -> bool:
        sql = """
        SELECT {} FROM {}.servers
        WHERE server = ($1);""".format(setting, self.schema)
        return await self.pool.fetchval(sql, server_id)

    async def get_user_stats(self, user_id) -> dict:
        user_stats = {}
        user_stats['global_requests'] = await self.__global_requests()

        user_request_sql = """
        SELECT COUNT(*) FROM {}.requests
        WHERE requester = ($1);
        """.format(self.schema)
        try:
            count = await self.pool.fetchval(user_request_sql, user_id)
            user_stats['user_requests'] = count
        except Exception as e:
            self.logger.warning(
                f'Exception occured while getting user requests: {e}')

        top_requests_sql = """
        SELECT title, medium, COUNT(title) FROM {}.requests
        WHERE requester = ($1)
        GROUP BY title, medium ORDER BY COUNT(title) DESC, title ASC LIMIT 5
        """.format(self.schema)
        try:
            top_requests = await self.pool.fetch(top_requests_sql, user_id)
            user_stats['top_requests'] = []
            for request in top_requests:
                user_stats['top_requests'].append(request)
        except Exception as e:
            self.logger.warning(
                f'Exception occured while getting user requests: {e}')

        request_rank = """
        SELECT row FROM
        (SELECT requester, count(1), ROW_NUMBER() over (ORDER BY COUNT(1) DESC)
            as row
        FROM {}.requests GROUP BY requester) as overallrequestrank
        WHERE requester = ($1)
        """.format(self.schema)

        try:
            user_stats['rank'] = int(
                await self.pool.fetchval(request_rank, user_id))
        except Exception as e:
            self.logger.warning(
                f'Exception occured while getting user request rank: {e}'
            )

        unique_requests = """
        SELECT COUNT(DISTINCT (title, medium))
        FROM {}.requests
        WHERE requester = ($1)
        """.format(self.schema)
        try:
            user_stats['unique_requests'] = int(
                await self.pool.fetchval(unique_requests, user_id))
        except Exception as e:
            self.logger.warning(
                f'Exception occured while getting user request rank: {e}'
            )

        return user_stats

    async def get_server_stats(self, server_id) -> dict:
        server_stats = {}
        server_stats['global_requests'] = await self.__global_requests()

        server_request_sql = """
        SELECT COUNT(*) FROM {}.requests
        WHERE server = ($1);
        """.format(self.schema)
        try:
            count = await self.pool.fetchval(server_request_sql, server_id)
            server_stats['server_requests'] = count
        except Exception as e:
            self.logger.warning(
                f'Exception occured while getting server requests: {e}')

        top_requests_sql = """
        SELECT title, medium, COUNT(title) FROM {}.requests
        WHERE server = ($1)
        GROUP BY title, medium ORDER BY COUNT(title) DESC, title ASC LIMIT 5
        """.format(self.schema)
        try:
            top_requests = await self.pool.fetch(top_requests_sql, server_id)
            server_stats['top_requests'] = []
            for request in top_requests:
                server_stats['top_requests'].append(request)
        except Exception as e:
            self.logger.warning(
                f'Exception occured while getting server requests: {e}')

        request_rank = """
        SELECT row FROM
        (SELECT server, count(1), ROW_NUMBER() over (ORDER BY COUNT(1) DESC)
            as row
        FROM {}.requests GROUP BY server) as overallrequestrank
        WHERE server = ($1)
        """.format(self.schema)

        try:
            server_stats['rank'] = int(
                await self.pool.fetchval(request_rank, server_id))
        except Exception as e:
            self.logger.warning(
                f'Exception occured while getting server request rank: {e}'
            )

        unique_requests = """
        SELECT COUNT(DISTINCT (title, medium))
        FROM {}.requests
        WHERE server = ($1)
        """.format(self.schema)
        try:
            server_stats['unique_requests'] = int(
                await self.pool.fetchval(unique_requests, server_id))
        except Exception as e:
            self.logger.warning(
                f'Exception occured while getting server request rank: {e}'
            )

        return server_stats