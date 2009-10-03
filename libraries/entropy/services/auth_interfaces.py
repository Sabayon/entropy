# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Services Authentication Interfaces}.

"""

import os
import time
import random
from entropy.services.skel import Authenticator, RemoteDatabase
from entropy.exceptions import *
from entropy.const import etpConst
from entropy.i18n import _

class phpBB3Auth(Authenticator,RemoteDatabase):

    from entropy import tools as entropyTools
    def __init__(self):
        Authenticator.__init__(self)
        RemoteDatabase.__init__(self)

        self.itoa64 = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        self.USER_NORMAL = 0
        self.USER_INACTIVE = 1
        self.USER_IGNORE = 2
        self.USER_FOUNDER = 3
        self.REGISTERED_USERS_GROUP = 7895
        self.ADMIN_GROUPS = [7893, 7898]
        self.MODERATOR_GROUPS = [484]
        self.DEVELOPER_GROUPS = [7900]
        self.USERNAME_LENGTH_RANGE = list(range(3,21))
        self.PASSWORD_LENGTH_RANGE = list(range(6,31))
        self.PRIVMSGS_NO_BOX = -3
        self.NOTIFY_EMAIL = 0
        self.FAKE_USERNAME = 'already_authed'
        self.USER_AGENT = "Entropy/%s (compatible; %s; %s: %s %s %s)" % (
                                        etpConst['entropyversion'],
                                        "Entropy",
                                        "UGC",
                                        os.uname()[0],
                                        os.uname()[4],
                                        os.uname()[2],
        )
        self.TABLE_PREFIX = 'phpbb_'
        self.do_update_session_table = True

    def validate_username_regex(self, username):
        allow_name_chars = self._get_config_value("allow_name_chars")
        if allow_name_chars == "USERNAME_CHARS_ANY":
            regex = '.+'
        elif allow_name_chars == "USERNAME_ALPHA_ONLY":
            regex = '[A-Za-z0-9]+'
        elif allow_name_chars == "USERNAME_ALPHA_SPACERS":
            regex = '[A-Za-z0-9-[\]_+ ]+'
        elif allow_name_chars == "USERNAME_LETTER_NUM":
            regex = '[a-zA-Z0-9]+'
        elif allow_name_chars == "USERNAME_LETTER_NUM_SPACERS":
            regex = '[-\]_+ [a-zA-Z0-9]+'
        else: # USERNAME_ASCII
            regex = '[\x01-\x7F]+'
        regex = "^%s$" % (regex,)
        import re
        myreg = re.compile(regex)
        if myreg.match(username):
            del myreg
            return True
        return False

    def does_username_exist(self, username, username_clean):
        self.check_connection()
        self.cursor.execute('SELECT user_id FROM '+self.TABLE_PREFIX+'users WHERE `username_clean` = %s OR LOWER(`username`) = %s', (username_clean,username.lower(),))
        data = self.cursor.fetchone()
        if not data: return False
        if not isinstance(data,dict): return False
        if 'user_id' not in data: return False
        return True

    def does_email_exist(self, email):
        self.check_connection()
        self.cursor.execute('SELECT user_id FROM '+self.TABLE_PREFIX+'users WHERE `user_email` = %s', (email,))
        data = self.cursor.fetchone()
        if not data: return False
        if not isinstance(data,dict): return False
        if 'user_id' not in data: return False
        return True

    def is_username_allowed(self, username):
        self.check_connection()
        self.cursor.execute('SELECT disallow_id FROM '+self.TABLE_PREFIX+'disallow WHERE `disallow_username` = %s', (username,))
        data = self.cursor.fetchone()
        if not data: return True
        if not isinstance(data,dict): return True
        if 'disallow_id' not in data: return True
        return False

    def validate_username_string(self, username, username_clean):

        try:
            x = unicode(username.encode('utf-8'),'raw_unicode_escape')
            del x
        except (UnicodeDecodeError,UnicodeEncodeError,):
            return False,'Invalid username'
        if ("&quot;" in username) or ("'" in username) or ('"' in username) or \
            (" " in username):
            return False,'Invalid username'

        try:
            valid = self.validate_username_regex(username)
        except:
            return False,'Username contains bad characters'
        if not valid:
            return False,'Invalid username'

        exists = self.does_username_exist(username, username_clean)
        if exists: return False,'Username already taken'

        allowed = self.is_username_allowed(username)
        if not allowed: return False,'Username not allowed'

        return True,'All fine'

    def _generate_email_hash(self, email):
        import binascii
        return str(binascii.crc32(email.lower())) + str(len(email))

    def activate_user(self, user_id):
        self.check_connection()
        self.cursor.execute('UPDATE '+self.TABLE_PREFIX+'users SET user_type = %s WHERE `user_id` = %s', (self.USER_NORMAL,user_id,))
        return True, user_id

    def generate_username_clean(self, username):
        import re
        username_clean = username.lower()
        username_clean = re.sub(r'(?:[\x00-\x1F\x7F]+|(?:\xC2[\x80-\x9F])+)', '', username_clean)
        username_clean = re.sub(r' {2,}',' ',username_clean)
        username_clean = username_clean.strip()
        return username_clean

    def register_user(self, username, password, email, activate = False):

        if len(username) not in self.USERNAME_LENGTH_RANGE:
            return False,'Username not in range'
        if len(password) not in self.PASSWORD_LENGTH_RANGE:
            return False,'Password not in range'
        valid = self.entropyTools.is_valid_email(email)
        if not valid:
            return False,'Invalid email'

        # create the clean one
        username_clean = self.generate_username_clean(username)

        # check username validity
        status, err_msg = self.validate_username_string(username, username_clean)
        if not status: return False,err_msg

        # check email
        exists = self.does_email_exist(email)
        if exists: return False,'Email already in use'

        # now cross fingers
        status, user_id = self.__register(username, username_clean, password, email, activate)
        if not status:
            return False, 'Invalid username (duplicated)'

        return True, user_id


    def __register(self, username, username_clean, password, email, activate):

        email_hash = self._generate_email_hash(email)
        password_hash = self._get_password_hash(password.encode('utf-8'))
        time_now = int(time.time())

        user_type = self.USER_INACTIVE
        if activate: user_type = self.USER_NORMAL

        registration_data = {
            'username': username,
            'username_clean': username_clean,
            'user_password': password_hash,
            'user_pass_convert': 0,
            'user_email': email.lower(),
            'user_email_hash': email_hash,
            'group_id': self.REGISTERED_USERS_GROUP,
            'user_type': user_type,
            'user_permissions': '',
            'user_timezone': self._get_config_value('board_timezone'),
            'user_dateformat': self._get_config_value('default_dateformat'),
            'user_lang': self._get_config_value('default_lang'),
            'user_style': self._get_config_value('default_style'),
            'user_actkey': '',
            'user_ip': '',
            'user_regdate': time_now,
            'user_passchg': time_now,
            'user_options': 895, # ? don't ask me
            'user_inactive_reason': 0,
            'user_inactive_time': 0,
            'user_lastmark': time_now,
            'user_lastvisit': 0,
            'user_lastpost_time': 0,
            'user_lastpage': '',
            'user_posts': 0,
            'user_dst': self._get_config_value('board_dst'),
            'user_colour': '',
            'user_occ': '',
            'user_interests': '',
            'user_avatar': '',
            'user_avatar_type': 0,
            'user_avatar_width': 0,
            'user_avatar_height': 0,
            'user_new_privmsg': 0,
            'user_unread_privmsg': 0,
            'user_last_privmsg': 0,
            'user_message_rules': 0,
            'user_full_folder': self.PRIVMSGS_NO_BOX,
            'user_emailtime': 0,
            'user_notify': 0,
            'user_notify_pm': 1,
            'user_notify_type': self.NOTIFY_EMAIL,
            'user_allow_pm': 1,
            'user_allow_viewonline': 1,
            'user_allow_viewemail': 1,
            'user_allow_massemail': 1,
            'user_sig': '',
            'user_sig_bbcode_uid': '',
            'user_sig_bbcode_bitfield': '',
            'user_form_salt': self._get_unique_id(),
        }

        sql = self._generate_sql('insert', self.TABLE_PREFIX+'users', registration_data)
        self.cursor.execute(sql)
        user_id = self.cursor.lastrowid

        # now insert into the default group
        group_data = {
            'user_id': user_id,
            'group_id': self.REGISTERED_USERS_GROUP,
            'user_pending': 0,
        }
        sql = self._generate_sql('insert', self.TABLE_PREFIX+'user_group', group_data)
        try:
            self.cursor.execute(sql)
        except self.mysql_exceptions.IntegrityError as e:
            # for sure it's about duplicated entry
            return False, 1062

        # set some misc config shit
        self._set_config_value('newest_user_id',user_id)
        self._set_config_value('newest_username',username)
        self._set_config_value('num_users',int(self._get_config_value('num_users'))+1)
        self.cursor.execute('SELECT group_colour FROM '+self.TABLE_PREFIX+'groups WHERE group_id = %s', (group_data['group_id'],))
        data = self.cursor.fetchone()
        gcolor = None
        if isinstance(data,dict):
            if 'group_colour' in data:
                gcolor = data['group_colour']
        if gcolor: self._set_config_value('newest_user_colour',gcolor)

        return True, user_id


    def login(self):
        self.check_connection()
        self.check_login_data()

        if 'username' not in self.login_data:
            raise PermissionDenied('PermissionDenied: %s' % (_('no username specified'),))
        elif 'password' not in self.login_data:
            raise PermissionDenied('PermissionDenied: %s' % (_('no password specified'),))

        if not self.login_data['password']:
            raise PermissionDenied('PermissionDenied: %s' % (_('empty password'),))
        elif not self.login_data['username']:
            raise PermissionDenied('PermissionDenied: %s' % (_('empty username'),))

        self.cursor.execute('SELECT * FROM '+self.TABLE_PREFIX+'users WHERE username = %s', (self.login_data['username'],))
        data = self.cursor.fetchone()
        if not data:
            raise PermissionDenied('PermissionDenied: %s' % (_('user not found'),))

        if data['user_pass_convert']:
            raise PermissionDenied('PermissionDenied: %s' % (
                    _('you need to login on the website to update your password format'),
                )
            )

        valid = self._phpbb3_check_hash(self.login_data['password'], data['user_password'])
        if not valid:
            raise PermissionDenied('PermissionDenied: %s' % (_('wrong password'),))

        user_type = data['user_type']
        if (user_type == self.USER_INACTIVE) or (user_type == self.USER_IGNORE):
            raise PermissionDenied('PermissionDenied: %s' % (_('user inactive'),))

        banned = self.is_user_banned(data['user_id'])
        if banned:
            raise PermissionDenied('PermissionDenied: %s' % (_('user banned'),))

        self.login_data.update(data)
        self.logged_in = True
        return self.logged_in

    def disconnect(self):
        if self.is_logged_in():
            self.logout()
        RemoteDatabase.disconnect(self)

    def logout(self):
        self.check_connection()
        self.check_login_data()
        self.logged_in = False
        self.login_data.clear()
        return True

    def get_user_data(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        self.cursor.execute('SELECT * FROM '+self.TABLE_PREFIX+'users WHERE user_id = %s', (self.login_data['user_id'],))
        return self.cursor.fetchone()

    def get_user_birthday(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        self.cursor.execute('SELECT user_birthday FROM '+self.TABLE_PREFIX+'users WHERE user_id = %s', (self.login_data['user_id'],))
        bday = self.cursor.fetchone()
        if not bday:
            return None
        elif 'user_birthday' not in bday:
            return None
        return bday['user_birthday']

    def get_username(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        self.cursor.execute('SELECT username_clean FROM '+self.TABLE_PREFIX+'users WHERE user_id = %s', (self.login_data['user_id'],))
        data = self.cursor.fetchone()
        if not data:
            return ''
        elif 'username_clean' not in data:
            return ''
        return data['username_clean']

    def is_developer(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        # search into phpbb_groups
        groups = self.get_user_groups()
        for group in groups:
            if group in self.DEVELOPER_GROUPS:
                return True

        return False

    def is_administrator(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        self.cursor.execute('SELECT user_type FROM '+self.TABLE_PREFIX+'users WHERE user_id = %s', (self.login_data['user_id'],))
        data = self.cursor.fetchone()
        if data:
            if data['user_type'] == self.USER_FOUNDER:
                return True

        # search into phpbb_groups
        groups = self.get_user_groups()
        for group in groups:
            if group in self.ADMIN_GROUPS:
                return True

        return False

    def is_moderator(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        # search into phpbb_groups
        groups = self.get_user_groups()
        for group in groups:
            if group in self.MODERATOR_GROUPS:
                return True

        return False

    def is_user(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        if self.is_moderator():
            return False
        elif self.is_administrator():
            return False
        elif self.is_developer():
            return False

        self.cursor.execute('SELECT user_type,user_id FROM '+self.TABLE_PREFIX+'users WHERE user_id = %s', (self.login_data['user_id'],))
        data = self.cursor.fetchone()
        if not data:
            return False
        if self.is_user_banned(data['user_id']):
            return False
        elif data['user_type'] in [self.USER_NORMAL]:
            return True

        return False

    # user == user_id
    def is_user_banned(self, user):
        self.check_connection()
        self.cursor.execute('SELECT ban_userid FROM '+self.TABLE_PREFIX+'banlist WHERE ban_userid = %s', (user,))
        data = self.cursor.fetchone()
        if data:
            return True
        return False

    def is_in_group(self, group):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        groups = self.get_user_groups()
        if isinstance(group,int):
            if group in groups:
                return True
        elif isinstance(group,basestring):
            self.cursor.execute('SELECT group_id FROM '+self.TABLE_PREFIX+'groups WHERE group_name = %s', (group,))
            data = self.cursor.fetchone()
            if not data:
                return False
            elif data['group_id'] in groups:
                return True

        return False

    def get_user_groups(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        self.cursor.execute('SELECT '+self.TABLE_PREFIX+'user_group.group_id,'+self.TABLE_PREFIX+'groups.group_name FROM '+self.TABLE_PREFIX+'user_group,'+self.TABLE_PREFIX+'users,'+self.TABLE_PREFIX+'groups WHERE '+self.TABLE_PREFIX+'users.user_id = %s and '+self.TABLE_PREFIX+'users.user_id = '+self.TABLE_PREFIX+'user_group.user_id and '+self.TABLE_PREFIX+'user_group.group_id = '+self.TABLE_PREFIX+'groups.group_id', (self.login_data['user_id'],))
        data = self.cursor.fetchall()
        mydata = {}
        for mydict in data:
            mydata[mydict['group_id']] = mydict['group_name']

        return mydata

    def get_user_group(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        self.cursor.execute('SELECT group_id FROM '+self.TABLE_PREFIX+'users WHERE user_id = %s', (self.login_data['user_id'],))
        data = self.cursor.fetchone()
        if data:
            if 'group_id' in data:
                return data['group_id']

        return -1

    def get_user_id(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        return self.login_data['user_id']

    def get_permission_data(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self.cursor.execute('SELECT user_permissions FROM '+self.TABLE_PREFIX+'users WHERE user_id = %s', (self.login_data['user_id'],))
        return self.cursor.fetchone()

    def update_email(self, email):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        email_hash = self._generate_email_hash(email)
        mydata = {
            'user_email_hash': email_hash,
            'user_email': email.lower(),
        }

        try:
            sql = self._generate_sql("update",self.TABLE_PREFIX+'users', mydata, 'user_id = %s' % (self.login_data['user_id'],))
            self.cursor.execute(sql)
            return True
        except Exception:
            return False

    def update_password_hash(self, password_hash):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        mydata = {
            'user_password': password_hash,
        }

        try:
            sql = self._generate_sql("update",self.TABLE_PREFIX+'users', mydata, 'user_id = %s' % (self.login_data['user_id'],))
            self.cursor.execute(sql)
            return True
        except Exception:
            return False

    def get_email(self):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()
        self.cursor.execute('SELECT user_email FROM '+self.TABLE_PREFIX+'users WHERE user_id = %s', (self.login_data['user_id'],))
        data = self.cursor.fetchone()
        if not data:
            return ''
        elif 'user_email' not in data:
            return ''
        return data['user_email']

    def update_user_id_profile(self, profile_data):
        self.check_connection()
        self.check_login_data()
        self.check_logged_in()

        # filter valid params
        valid_params = [
            "user_icq","user_yim","user_msnm",
            "user_jabber","user_website","user_from",
            "user_interests","user_occ","user_birthday",
            "user_sig"
        ]

        my_params = {}
        for param in valid_params:
            d = profile_data.get(param)
            if d == None: continue
            my_params[param] = d

        if not my_params:
            return False,'no parameters'


        # validate parameters
        b_day = my_params.get('user_birthday')
        if isinstance(b_day,basestring):
            import re
            myre = re.compile("(0[1-9]|[12][0-9]|3[01])[-](0[1-9]|1[012])[-](19|20)\d\d")
            if not myre.match(b_day):
                del my_params['user_birthday']

        try:
            sql = self._generate_sql("update",self.TABLE_PREFIX+'users', my_params, 'user_id = %s' % (self.login_data['user_id'],))
            self.cursor.execute(sql)
            return True, None
        except Exception as e:
            return False, str(e)


    def _set_config_value(self, config_name, data):
        self.cursor.execute('UPDATE '+self.TABLE_PREFIX+'config SET config_value = %s WHERE config_name = %s',(data,config_name,))

    def _get_config_value(self, config_name):
        self.check_connection()
        self.cursor.execute('SELECT config_value FROM '+self.TABLE_PREFIX+'config WHERE config_name = %s',(config_name,))
        myconfig = self.cursor.fetchone()
        if isinstance(myconfig,dict):
            if 'config_value' in myconfig:
                return myconfig['config_value']
        return None

    def _update_session_table(self, user_id, ip_address):
        self.check_connection()
        time_now = int(time.time())
        autologin = self._get_config_value("allow_autologin")
        self.cursor.execute('SELECT user_allow_viewonline FROM '+self.TABLE_PREFIX+'users WHERE user_id = %s', (user_id,))
        myuserprefs = self.cursor.fetchone()
        session_admin = 0
        session_data = {
            'session_id': None,
            'session_user_id': user_id,
            'session_last_visit': time_now,
            'session_start': time_now,
            'session_time': time_now,
            'session_ip': ip_address,
            'session_browser': self.USER_AGENT,
            'session_forwarded_for': '',
            'session_page': 'index.php',
            'session_viewonline': myuserprefs['user_allow_viewonline'],
            'session_autologin': autologin,
            'session_admin': session_admin,
            'session_forum_id': 0,
        }
        import hashlib
        m = hashlib.md5()
        m.update(str(user_id)+str(time_now)+str(self.USER_AGENT)+str(ip_address)+str(autologin)+str(myuserprefs['user_allow_viewonline']))
        session_data['session_id'] = m.hexdigest()

        self.cursor.execute('SELECT * FROM '+self.TABLE_PREFIX+'sessions WHERE session_user_id = %s', (user_id,))
        mydata = self.cursor.fetchone()
        do_update = False
        if mydata:
            do_update = True
            # update
            session_data['session_id'] = mydata['session_id']
            session_data['session_viewonline'] = mydata['session_viewonline']
            session_data['session_autologin'] = mydata['session_autologin']
            session_data['session_forwarded_for'] = mydata['session_forwarded_for']
            session_data['session_forum_id'] = mydata['session_forum_id']
            session_data['session_page'] = mydata['session_page']
            session_data['session_browser'] = mydata['session_browser']
            session_data['session_admin'] = mydata['session_admin']

        if do_update:
            where = "session_id = '%s'" % (session_data['session_id'],)
            del session_data['session_id']
            sql = self._generate_sql('update', self.TABLE_PREFIX+'sessions', session_data, where)
        else:
            sql = self._generate_sql('insert', self.TABLE_PREFIX+'sessions', session_data)
        if sql:
            self.cursor.execute(sql)
            self.dbconn.commit()


    def _is_ip_banned(self, ip):
        self.check_connection()
        self.cursor.execute('SELECT ban_ip FROM '+self.TABLE_PREFIX+'banlist WHERE ban_ip = %s', (ip,))
        data = self.cursor.fetchone()
        if data:
            return True
        return False

    def _get_unique_id(self):
        import hashlib
        m = hashlib.md5()
        rnd = str(abs(hash(os.urandom(1))))
        m.update(rnd)
        x = m.hexdigest()[:-16]
        del m
        return x

    def _get_random_number(self):
        myrand = 0
        low_n = 100000
        high_n = 999999
        while (myrand < low_n) or (myrand > high_n):
            try:
                myrand = hash(os.urandom(1))%high_n
            except NotImplementedError:
                random.seed()
                myrand = random.randint(low_n,high_n)
        return myrand

    def _get_password_hash(self, password):

        #random_state = self._get_unique_id()
        myrandom = str(self._get_random_number())

        myhash = self._hash_crypt_private(password, self._hash_gensalt_private(myrandom))

        if len(myhash) == 34:
            return myhash

        import hashlib
        m = hashlib.md5()
        m.update(myhash)
        return m.hexdigest()


    def _hash_gensalt_private(self, myinput, iteration_count_log2 = 6):

        if (iteration_count_log2 < 4) or (iteration_count_log2 > 31):
            iteration_count_log2 = 8

        myoutput = '$H$'
        myoutput += self.itoa64[min(iteration_count_log2 + 5,30)]
        myoutput += self._hash_encode64(myinput, 6)

        return myoutput

    def _hash_crypt_private(self, password, setting):

        myoutput = '*'
        # Check for correct hash
        if setting[:3] != '$H$':
            return myoutput

        count_log2 = self.itoa64.find(setting[3])
        if count_log2 == -1: count_log2 = 0

        if (count_log2 < 7) or (count_log2 > 30):
            return myoutput

        count = 1 << count_log2
        salt = setting[4:12]

        if len(salt) != 8:
            return myoutput

        import hashlib
        m = hashlib.md5()
        m.update(salt+password)
        myhash = m.digest()
        while count:
            m = hashlib.md5()
            m.update(myhash+password)
            myhash = m.digest()
            count -= 1

        myoutput = setting[:12]
        myoutput += self._hash_encode64(myhash, 16)

        return myoutput

    def _hash_encode64(self, myinput, count):

        output = ''
        i = 0
        while i < count:

            value = ord(myinput[i])
            i += 1
            output += self.itoa64[value & 0x3f]
            if i < count:
                value |= ord(myinput[i]) << 8

            output += self.itoa64[(value >> 6) & 0x3f]

            if i >= count:
                break
            i += 1

            if i < count:
                value |= ord(myinput[i]) << 16

            output += self.itoa64[(value >> 12) & 0x3f]

            if (i >= count):
                break
            i += 1

            output += self.itoa64[(value >> 18) & 0x3f]

        return output

    def _phpbb3_check_hash(self, password, myhash):

        if len(myhash) == 34:
            return self._hash_crypt_private(password, myhash) == myhash

        import hashlib
        m = hashlib.md5()
        m.update(password)
        rhash = m.hexdigest()
        return rhash == myhash
