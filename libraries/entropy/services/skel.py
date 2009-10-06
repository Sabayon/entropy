# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Services Stub Interfaces}.

"""
from entropy.const import const_convert_to_unicode
from entropy.tools import escape
from entropy.exceptions import *
from entropy.i18n import _

class SocketCommands:

    def __str__(self):
        return self.inst_name

    inst_name = 'command-skel'
    def __init__(self, HostInterface, inst_name = 'command-skel'):
        self.HostInterface = HostInterface
        self.no_acked_commands = []
        self.termination_commands = []
        self.initialization_commands = []
        self.login_pass_commands = []
        self.no_session_commands = []
        self.raw_commands = []
        self.config_commands = []
        self.valid_commands = set()
        self.inst_name = inst_name

    def register(
            self,
            valid_commands,
            no_acked_commands,
            termination_commands,
            initialization_commands,
            login_pass_commads,
            no_session_commands,
            raw_commands,
            config_commands
        ):
        valid_commands.update(self.valid_commands)
        no_acked_commands.extend(self.no_acked_commands)
        termination_commands.extend(self.termination_commands)
        initialization_commands.extend(self.initialization_commands)
        login_pass_commads.extend(self.login_pass_commands)
        no_session_commands.extend(self.no_session_commands)
        raw_commands.extend(self.raw_commands)
        config_commands.extend(self.config_commands)

class SocketAuthenticator:

    def __init__(self, HostInterface):
        self.HostInterface = HostInterface
        self.session = None

    def set_session(self, session):
        self.session = session

class RemoteDatabase:

    def __init__(self):
        self.dbconn = None
        self.cursor = None
        self.plain_cursor = None
        self.escape_string = escape
        self.connection_data = {}
        try:
            import MySQLdb, _mysql_exceptions
            from MySQLdb.constants import FIELD_TYPE
            from MySQLdb.converters import conversions
        except ImportError:
            raise LibraryNotFound('LibraryNotFound: dev-python/mysql-python not found')
        self.mysql = MySQLdb
        self.mysql_exceptions = _mysql_exceptions
        self.FIELD_TYPE = FIELD_TYPE
        self.conversion_dict = conversions.copy()
        self.conversion_dict[self.FIELD_TYPE.DECIMAL] = int
        self.conversion_dict[self.FIELD_TYPE.LONG] = int
        self.conversion_dict[self.FIELD_TYPE.FLOAT] = float
        self.conversion_dict[self.FIELD_TYPE.NEWDECIMAL] = float

    def check_connection(self):
        if self.dbconn == None:
            raise ConnectionError('ConnectionError: %s' % (_("not connected to database"),))
        self._check_needed_reconnect()

    def _check_needed_reconnect(self):
        if self.dbconn == None:
            return
        try:
            self.dbconn.ping()
        except self.mysql_exceptions.OperationalError as e:
            if e[0] != 2006:
                raise
            else:
               self.connect()
               return True
        return False

    def _raise_not_implemented_error(self):
        raise NotImplementedError('NotImplementedError: %s' % (_('method not implemented'),))

    def set_connection_data(self, data):
        self.connection_data = data.copy()
        if 'converters' not in self.connection_data and self.conversion_dict:
            self.connection_data['converters'] = self.conversion_dict.copy()

    def check_connection_data(self):
        if not self.connection_data:
            raise PermissionDenied('ConnectionError: %s' % (_("no connection data"),))

    def connect(self):
        kwargs = {}
        keys = [
            ('host', "hostname"),
            ('user', "username"),
            ('passwd', "password"),
            ('db', "dbname"),
            ('port', "port"),
            ('conv', "converters"), # mysql type converter dict
        ]
        for ckey, dkey in keys:
            if dkey not in self.connection_data:
                continue
            kwargs[ckey] = self.connection_data.get(dkey)

        try:
            self.dbconn = self.mysql.connect(**kwargs)
        except self.mysql_exceptions.OperationalError as e:
            raise ConnectionError('ConnectionError: %s' % (e,))
        self.plain_cursor = self.dbconn.cursor()
        self.cursor = self.mysql.cursors.DictCursor(self.dbconn)
        self.escape_string = self.dbconn.escape_string
        return True

    def disconnect(self):
        self.check_connection()
        self.escape_string = escape
        if hasattr(self.cursor, 'close'):
            self.cursor.close()
        if hasattr(self.dbconn, 'close'):
            self.dbconn.close()
        self.dbconn = None
        self.cursor = None
        self.plain_cursor = None
        self.connection_data.clear()
        return True

    def commit(self):
        self.check_connection()
        return self.dbconn.commit()

    def execute_script(self, myscript):
        pty = None
        for line in myscript.split(";"):
            line = line.strip()
            if not line:
                continue
            pty = self.cursor.execute(line)
        return pty

    def execute_query(self, *args):
        return self.cursor.execute(*args)

    def execute_many(self, query, myiter):
        return self.cursor.executemany(query, myiter)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchmany(self, *args, **kwargs):
        return self.cursor.fetchmany(*args,**kwargs)

    def lastrowid(self):
        return self.cursor.lastrowid

    def table_exists(self, table):
        self.check_connection()
        self.cursor.execute("show tables like %s", (table,))
        rslt = self.cursor.fetchone()
        if rslt:
            return True
        return False

    def column_in_table_exists(self, table, column):
        t_ex = self.table_exists(table)
        if not t_ex:
            return False
        self.cursor.execute("show columns from "+table)
        data = self.cursor.fetchall()
        for row in data:
            if row['Field'] == column:
                return True
        return False

    def fetchall2set(self, item):
        mycontent = set()
        for x in item:
            mycontent |= set(x)
        return mycontent

    def fetchall2list(self, item):
        content = []
        for x in item:
            content += list(x)
        return content

    def fetchone2list(self, item):
        return list(item)

    def fetchone2set(self, item):
        return set(item)

    def _generate_sql(self, action, table, data, where = ''):
        sql = ''
        keys = sorted(data.keys())
        if action == "update":
            sql += 'UPDATE %s SET ' % (self.escape_string(table),)
            keys_data = []
            for key in keys:
                keys_data.append("%s = '%s'" % (
                        self.escape_string(key),
                        self.escape_string(
                            const_convert_to_unicode(data[key], 'utf-8').encode('utf-8')).decode('utf-8')
                    )
                )
            sql += ', '.join(keys_data)
            sql += ' WHERE %s' % (where,)
        elif action == "insert":
            sql = 'INSERT INTO %s (%s) VALUES (%s)' % (
                self.escape_string(table),
                ', '.join([self.escape_string(x) for x in keys]),
                ', '.join(["'" + \
                    self.escape_string(
                    const_convert_to_unicode(data[x], 'utf-8').encode('utf-8')).decode('utf-8') + \
                    "'" for x in keys])
            )
        return sql

class Authenticator:

    def __init__(self):
        self.login_data = {}
        self.logged_in = False

    def check_login(self):
        if not self.logged_in:
            raise PermissionDenied('PermissionDenied: %s' % (_("not logged in"),))

    def set_login_data(self, data):
        self.login_data = data.copy()

    def check_login_data(self):
        if not self.login_data:
            raise PermissionDenied('PermissionDenied: %s' % (_("no login data"),))

    def check_logged_in(self):
        if not self.is_logged_in():
            raise PermissionDenied('PermissionDenied: %s' % (_("not logged in"),))

    def _raise_not_implemented_error(self):
        raise NotImplementedError('NotImplementedError: %s' % (_('method not implemented'),))

    def check_connection(self):
        pass

    def login(self):
        self.check_connection()
        self.check_login_data()
        self._raise_not_implemented_error()
        self.logged_in = True
        return True

    def logout(self):
        self.check_connection()
        self.check_login_data()
        self._raise_not_implemented_error()
        return True

    def is_developer(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return True

    def is_administrator(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return True

    def is_moderator(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return True

    def is_user(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return True

    def is_user_banned(self, user):
        self.check_connection()
        self._raise_not_implemented_error()
        return False

    def is_in_group(self, group):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return True

    def get_user_groups(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return {}

    def get_user_group(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return -1

    def get_user_id(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return -1

    def is_logged_in(self):
        return self.logged_in

    def get_permission_data(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return {}

    def get_user_data(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return {}

    def get_username(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self._raise_not_implemented_error()
        return {}

