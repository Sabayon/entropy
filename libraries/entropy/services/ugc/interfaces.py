# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

from __future__ import with_statement
import os
import sys
import time
import subprocess
import shutil
from entropy.services.skel import RemoteDatabase
from entropy.exceptions import *
from entropy.const import etpConst, etpUi, etpCache, const_setup_perms, const_set_chmod, const_setup_file
from entropy.output import brown, bold, blue
from entropy.i18n import _

class Server(RemoteDatabase):

    SQL_TABLES = {
        'entropy_base': """
            CREATE TABLE `entropy_base` (
            `idkey` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `key` VARCHAR( 255 )  collate utf8_bin NOT NULL,
            KEY `key` (`key`)
            );
        """,
        'entropy_votes': """
            CREATE TABLE `entropy_votes` (
            `idvote` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `idkey` INT UNSIGNED NOT NULL,
            `userid` INT UNSIGNED NOT NULL,
            `vdate` DATE NOT NULL,
            `vote` TINYINT NOT NULL,
            `ts` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY  (`idkey`) REFERENCES `entropy_base` (`idkey`)
            );
        """,
        'entropy_user_scores': """
            CREATE TABLE `entropy_user_scores` (
            `userid` INT UNSIGNED NOT NULL PRIMARY KEY,
            `score` INT UNSIGNED NOT NULL DEFAULT 0
            );
        """,
        'entropy_downloads': """
            CREATE TABLE `entropy_downloads` (
            `iddownload` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `idkey` INT UNSIGNED NOT NULL,
            `ddate` DATE NOT NULL,
            `count` INT UNSIGNED NULL DEFAULT '0',
            KEY `idkey` (`idkey`,`ddate`),
            KEY `idkey_2` (`idkey`),
            FOREIGN KEY  (`idkey`) REFERENCES `entropy_base` (`idkey`)
            );
        """,
        'entropy_downloads_data': """
            CREATE TABLE `entropy_downloads_data` (
            `iddownload` INT UNSIGNED NOT NULL,
            `ip_address` VARCHAR(40) NULL DEFAULT '',
            `entropy_ip_locations_id` INT UNSIGNED NULL DEFAULT 0,
            FOREIGN KEY  (`iddownload`) REFERENCES `entropy_downloads` (`iddownload`)
            );
        """,
        'entropy_docs': """
            CREATE TABLE `entropy_docs` (
            `iddoc` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `idkey` INT UNSIGNED NOT NULL,
            `userid` INT UNSIGNED NOT NULL,
            `username` VARCHAR( 255 ),
            `iddoctype` TINYINT NOT NULL,
            `ddata` TEXT NOT NULL,
            `title` VARCHAR( 512 ),
            `description` VARCHAR( 4000 ),
            `ts` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY `idkey` (`idkey`),
            KEY `userid` (`userid`),
            KEY `idkey_2` (`idkey`,`userid`,`iddoctype`),
            KEY `title` (`title`(333)),
            KEY `description` (`description`(333)),
            FOREIGN KEY  (`idkey`) REFERENCES `entropy_base` (`idkey`)
            );
        """,
        'entropy_doctypes': """
            CREATE TABLE `entropy_doctypes` (
            `iddoctype` TINYINT NOT NULL PRIMARY KEY,
            `description` TEXT NOT NULL
            );
        """,
        'entropy_docs_keywords': """
            CREATE TABLE `entropy_docs_keywords` (
            `iddoc` INT UNSIGNED NOT NULL,
            `keyword` VARCHAR( 100 ),
            KEY `keyword` (`keyword`),
            FOREIGN KEY  (`iddoc`) REFERENCES `entropy_docs` (`iddoc`)
            );
        """,
        'entropy_distribution_usage': """
            CREATE TABLE `entropy_distribution_usage` (
            `entropy_distribution_usage_id` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `entropy_branches_id` INT NOT NULL,
            `entropy_release_strings_id` INT NOT NULL,
            `ts` TIMESTAMP ON UPDATE CURRENT_TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            `ip_address` VARCHAR( 15 ),
            `entropy_ip_locations_id` INT UNSIGNED NULL DEFAULT 0,
            `creation_date` DATETIME DEFAULT NULL,
            `hits` INT UNSIGNED NULL DEFAULT 0,
            FOREIGN KEY  (`entropy_branches_id`) REFERENCES `entropy_branches` (`entropy_branches_id`),
            FOREIGN KEY  (`entropy_release_strings_id`) REFERENCES `entropy_release_strings` (`entropy_release_strings_id`),
            KEY `ip_address` (`ip_address`),
            KEY `entropy_ip_locations_id` (`entropy_ip_locations_id`)
            );
        """,
        'entropy_hardware_usage': """
            CREATE TABLE `entropy_hardware_usage` (
            `entropy_hardware_usage_id` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `entropy_distribution_usage_id` INT UNSIGNED NOT NULL,
            `entropy_hardware_hash` VARCHAR ( 64 ),
            FOREIGN KEY  (`entropy_distribution_usage_id`) REFERENCES `entropy_distribution_usage` (`entropy_distribution_usage_id`)
            );
        """,
        #'entropy_hardware_store': """
        #    CREATE TABLE `entropy_hardware_store` (
        #    `entropy_hardware_store_id` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        #    `entropy_hardware_usage_id` INT UNSIGNED NOT NULL,
        #    `uname` VARCHAR ( 64 ),
        #    FOREIGN KEY  (`entropy_hardware_usage_id`) REFERENCES `entropy_hardware_usage` (`entropy_hardware_usage_id`)
        #    );
        #""",
        'entropy_branches': """
            CREATE TABLE `entropy_branches` (
            `entropy_branches_id` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `entropy_branch` VARCHAR( 100 )
            );
        """,
        'entropy_release_strings': """
            CREATE TABLE `entropy_release_strings` (
            `entropy_release_strings_id` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `release_string` VARCHAR( 255 )
            );
        """,
        'entropy_ip_locations': """
            CREATE TABLE `entropy_ip_locations` (
            `entropy_ip_locations_id` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `ip_latitude` FLOAT( 8,5 ),
            `ip_longitude` FLOAT( 8,5 ),
            KEY `ip_locations_lat_lon` (`ip_latitude`,`ip_longitude`)
            );
        """,
    }
    VOTE_RANGE = etpConst['ugc_voterange'] # [1, 2, 3, 4, 5]
    VIRUS_CHECK_EXEC = '/usr/bin/clamscan'
    VIRUS_CHECK_ARGS = []
    gdata = None
    YouTube = None
    YouTubeService = None
    entropy_docs_title_len = 512
    entropy_docs_description_len = 4000
    entropy_docs_keyword_len = 100
    COMMENTS_SCORE_WEIGHT = 5
    DOCS_SCORE_WEIGHT = 10
    VOTES_SCORE_WEIGHT = 2
    STATS_MAP = {
        'installer': "installer",
    }

    '''
        dependencies:
            dev-python/gdata
    '''
    def __init__(self, connection_data, store_path, store_url = ''):
        import entropy.dump as dumpTools
        import entropy.tools as entropyTools
        from entropy.misc import EntropyGeoIP
        self.EntropyGeoIP = EntropyGeoIP
        self.entropyTools, self.dumpTools = entropyTools, dumpTools
        self.store_url = store_url
        self.FLOOD_INTERVAL = 30
        self.DOC_TYPES = etpConst['ugc_doctypes'].copy()
        self.UPLOADED_DOC_TYPES = [
            self.DOC_TYPES['image'],
            self.DOC_TYPES['generic_file']
        ]
        RemoteDatabase.__init__(self)
        self.set_connection_data(connection_data)
        self.connect()
        self.initialize_tables()
        self.initialize_doctypes()
        self.setup_store_path(store_path)
        from entropy.core import SystemSettings
        self.__system_settings = SystemSettings()
        self.system_name = self.__system_settings['system']['name']
        from datetime import datetime
        self.datetime = datetime
        try:
            import gdata
            import gdata.youtube
            import gdata.youtube.service
            self.gdata = gdata
            self.YouTube = gdata.youtube
            self.YouTubeService = gdata.youtube.service
        except ImportError:
            pass

        self.cached_results = {
            #'get_ugc_allvotes': (self.get_ugc_allvotes, [], {}, 86400),
            'get_ugc_alldownloads': (self.get_ugc_alldownloads, [], {}, 86400),
            #'get_users_scored_count': (self.get_users_scored_count, [], {}, 86400),
            'get_total_downloads_count': (self.get_total_downloads_count, [], {}, 7200),
        }

    def get_current_time(self):
        return int(time.time())

    def cache_results(self):
        for cache_item in self.cached_results:
            fdata = self.cached_results.get(cache_item)
            if fdata == None: return
            func, args, kwargs, exp_time = fdata
            key = self.get_cache_item_key(cache_item)
            r = func(*args,**kwargs)
            self.dumpTools.dumpobj(key, r)

    def get_cache_item_key(self, cache_item):
        return os.path.join(etpCache['ugc_srv_cache'],cache_item)

    def cache_result(self, cache_item, r):
        if not self.cached_results.get(cache_item): return None
        key = self.get_cache_item_key(cache_item)
        self.dumpTools.dumpobj(key, r)

    def _get_geoip_data_from_ip_address(self, ip_address):
        geoip_dbpath = self.connection_data.get('geoip_dbpath','')
        if os.path.isfile(geoip_dbpath) and os.access(geoip_dbpath,os.R_OK):
            try:
                geo = self.EntropyGeoIP(geoip_dbpath)
                return geo.get_geoip_record_from_ip(ip_address)
            except: # lame, but I don't know what exceptions are thrown
                pass

    # expired get_ugc_alldownloads 0 86400 1228577077
    def get_cached_result(self, cache_item):
        fdata = self.cached_results.get(cache_item)
        if fdata == None: return None
        func, args, kwargs, exp_time = fdata

        key = self.get_cache_item_key(cache_item)
        cur_time = self.get_current_time()
        cache_time = self.dumpTools.getobjmtime(key)
        if (cache_time + exp_time) < cur_time:
            # expired
            return None
        return self.dumpTools.loadobj(key)

    def setup_store_path(self, path):
        path = os.path.realpath(path)
        if not os.path.isabs(path):
            raise PermissionDenied('PermissionDenied: %s' % (_("not a valid directory path"),))
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except OSError, e:
                raise PermissionDenied('PermissionDenied: %s' % (e,))
            if etpConst['entropygid'] != None:
                const_setup_perms(path,etpConst['entropygid'])
        self.STORE_PATH = path

    def initialize_tables(self):
        notable = False
        for table in self.SQL_TABLES:
            if self.table_exists(table):
                continue
            notable = True
            self.execute_script(self.SQL_TABLES[table])
        if notable:
            self.commit()

    def initialize_doctypes(self):
        for mydoctype in self.DOC_TYPES:
            if self.is_iddoctype_available(self.DOC_TYPES[mydoctype]):
                continue
            self.insert_iddoctype(self.DOC_TYPES[mydoctype],mydoctype)

    def is_iddoctype_available(self, iddoctype):
        self.check_connection()
        rows = self.execute_query('SELECT `iddoctype` FROM entropy_doctypes WHERE `iddoctype` = %s', (iddoctype,))
        if rows:
            return True
        return False

    def is_pkgkey_available(self, key):
        self.check_connection()
        rows = self.execute_query('SELECT `idkey` FROM entropy_base WHERE `key` = %s', (key,))
        if rows:
            return True
        return False

    def is_iddoc_available(self, iddoc):
        self.check_connection()
        rows = self.execute_query('SELECT `iddoc` FROM entropy_docs WHERE `iddoc` = %s', (iddoc,))
        if rows:
            return True
        return False

    def insert_iddoctype(self, iddoctype, description, do_commit = False):
        self.check_connection()
        self.execute_query('INSERT INTO entropy_doctypes VALUES (%s,%s)', (iddoctype,description,))
        if do_commit: self.commit()

    def insert_pkgkey(self, key, do_commit = False):
        self.check_connection()
        self.execute_query('INSERT INTO entropy_base VALUES (%s,%s)', (None,key,))
        myid = self.lastrowid()
        if do_commit: self.commit()
        return myid

    def insert_download(self, key, ddate, count = 0, do_commit = False):
        self.check_connection()
        idkey = self.handle_pkgkey(key)
        self.execute_query('INSERT INTO entropy_downloads VALUES (%s,%s,%s,%s)', (None,idkey,ddate,count))
        myid = self.lastrowid()
        if do_commit: self.commit()
        return myid

    def insert_entropy_branch(self, branch, do_commit = False):
        self.check_connection()
        self.execute_query('INSERT INTO entropy_branches VALUES (%s,%s)', (None,branch,))
        myid = self.lastrowid()
        if do_commit: self.commit()
        return myid

    def insert_entropy_release_string(self, release_string, do_commit = False):
        self.check_connection()
        self.execute_query('INSERT INTO entropy_release_strings VALUES (%s,%s)', (None,release_string,))
        myid = self.lastrowid()
        if do_commit: self.commit()
        return myid

    def insert_entropy_ip_locations_id(self, ip_latitude, ip_longitude, do_commit = False):
        self.check_connection()
        self.execute_query('INSERT INTO entropy_ip_locations VALUES (%s,%s,%s)', (None,ip_latitude,ip_longitude,))
        myid = self.lastrowid()
        if do_commit: self.commit()
        return myid

    def handle_entropy_ip_locations_id(self, ip_addr):
        entropy_ip_locations_id = 0
        geo_data = self._get_geoip_data_from_ip_address(ip_addr)
        if isinstance(geo_data,dict):
            ip_lat = geo_data.get('latitude')
            ip_long = geo_data.get('longitude')
            if isinstance(ip_lat,float) and isinstance(ip_long,float):
                ip_lat = round(ip_lat,5)
                ip_long = round(ip_long,5)
                entropy_ip_locations_id = self.get_entropy_ip_locations_id(ip_lat, ip_long)
                if entropy_ip_locations_id == -1:
                    entropy_ip_locations_id = self.insert_entropy_ip_locations_id(ip_lat, ip_long)
        return entropy_ip_locations_id

    def update_download(self, iddownload, do_commit = False):
        self.check_connection()
        self.execute_query('UPDATE entropy_downloads SET `count` = `count`+1 WHERE `iddownload` = %s', (iddownload,))
        if do_commit: self.commit()
        return iddownload

    def store_download_data(self, iddownloads, ip_addr, do_commit = False):
        entropy_ip_locations_id = self.handle_entropy_ip_locations_id(ip_addr)
        mydata = [(x,ip_addr,entropy_ip_locations_id,) for x in iddownloads]
        self.execute_many('INSERT INTO entropy_downloads_data VALUES (%s,%s,%s)', mydata)
        if do_commit: self.commit()

    def get_date(self):
        mytime = time.time()
        mydate = self.datetime.fromtimestamp(mytime)
        mydate = self.datetime(mydate.year,mydate.month,mydate.day)
        return mydate

    def get_datetime(self):
        mytime = time.time()
        mydate = self.datetime.fromtimestamp(mytime)
        mydate = self.datetime(mydate.year,mydate.month,mydate.day,mydate.hour,mydate.minute,mydate.second)
        return mydate

    def get_iddownload(self, key, ddate):
        self.check_connection()
        idkey = self.handle_pkgkey(key)
        self.execute_query('SELECT `iddownload` FROM entropy_downloads WHERE `idkey` = %s AND `ddate` = %s', (idkey,ddate,))
        data = self.fetchone()
        if data:
            return data['iddownload']
        return -1

    def get_idkey(self, key):
        self.check_connection()
        self.execute_query('SELECT `idkey` FROM entropy_base WHERE `key` = %s', (key,))
        data = self.fetchone()
        if data:
            return data['idkey']
        return -1

    def get_iddoctype(self, iddoc):
        self.check_connection()
        self.execute_query('SELECT `iddoctype` FROM entropy_docs WHERE `iddoc` = %s', (iddoc,))
        data = self.fetchone()
        if data:
            return data['iddoctype']
        return -1

    def get_entropy_branches_id(self, branch):
        self.check_connection()
        self.execute_query('SELECT `entropy_branches_id` FROM entropy_branches WHERE `entropy_branch` = %s', (branch,))
        data = self.fetchone()
        if data:
            return data['entropy_branches_id']
        return -1

    def get_entropy_release_strings_id(self, release_string):
        self.check_connection()
        self.execute_query('SELECT `entropy_release_strings_id` FROM entropy_release_strings WHERE `release_string` = %s', (release_string,))
        data = self.fetchone()
        if data:
            return data['entropy_release_strings_id']
        return -1

    def get_entropy_ip_locations_id(self, ip_latitude, ip_longitude):
        self.check_connection()
        self.execute_query("""
        SELECT `entropy_ip_locations_id` FROM 
        entropy_ip_locations WHERE 
        `ip_latitude` = %s AND `ip_longitude` = %s""", (ip_latitude,ip_longitude,))
        data = self.fetchone()
        if data:
            return data['entropy_ip_locations_id']
        return -1

    def get_pkgkey(self, idkey):
        self.check_connection()
        self.execute_query('SELECT `key` FROM entropy_base WHERE `idkey` = %s', (idkey,))
        data = self.fetchone()
        if data: return data['key']

    def get_ugc_metadata(self, pkgkey):
        self.check_connection()
        metadata = {
            'vote': 0.0,
            'downloads': 0,
        }
        self.execute_query('SELECT * FROM entropy_docs,entropy_base WHERE entropy_base.`idkey` = entropy_docs.`idkey` AND entropy_base.`key` = %s', (pkgkey,))
        metadata['docs'] = [self._get_ugc_extra_metadata(x) for x \
            in self.fetchall()]
        metadata['vote'] = self.get_ugc_vote(pkgkey)
        metadata['downloads'] = self.get_ugc_downloads(pkgkey)
        return metadata

    def get_ugc_keywords(self, iddoc):
        self.execute_query('SELECT `keyword` FROM entropy_docs_keywords WHERE `iddoc` = %s order by `keyword`', (iddoc,))
        return [x.get('keyword') for x in self.fetchall() if x.get('keyword')]

    def get_ugc_metadata_doctypes(self, pkgkey, typeslist):
        self.check_connection()
        metadata = []
        self.execute_query("""
            SELECT * FROM entropy_docs,entropy_base WHERE 
            entropy_docs.`idkey` = entropy_base.`idkey` AND 
            entropy_base.`key` = %s AND 
            entropy_docs.`iddoctype` IN %s 
            ORDER BY entropy_docs.`ts` ASC""", (pkgkey, typeslist,))
        return [self._get_ugc_extra_metadata(x) for x in self.fetchall()]

    def get_ugc_metadata_doctypes_by_identifiers(self, identifiers, typeslist):
        self.check_connection()
        identifiers = list(identifiers)
        if len(identifiers) < 2:
            identifiers += [0]
        typeslist = list(typeslist)
        if len(typeslist) < 2:
            typeslist += [0]
        self.execute_query('SELECT * FROM entropy_docs WHERE `iddoc` IN %s AND `iddoctype` IN %s', (identifiers,typeslist,))
        return [self._get_ugc_extra_metadata(x) for x in self.fetchall()]

    def get_ugc_metadata_by_identifiers(self, identifiers):
        self.check_connection()
        identifiers = list(identifiers)
        if len(identifiers) < 2:
            identifiers += [0]
        self.execute_query('SELECT * FROM entropy_docs WHERE `iddoc` IN %s', (identifiers,))
        return [self._get_ugc_extra_metadata(x) for x in self.fetchall()]

    def _get_ugc_extra_metadata(self, mydict):
        mydict['store_url'] = None
        mydict['keywords'] = self.get_ugc_keywords(mydict['iddoc'])
        if mydict.has_key("key"):
            mydict['pkgkey'] = mydict['key']
        else:
            mydict['pkgkey'] = self.get_pkgkey(mydict['idkey'])
        # for binary files, get size too
        mydict['size'] = 0
        if mydict['iddoctype'] in self.UPLOADED_DOC_TYPES:
            myfilename = mydict['ddata']
            if not isinstance(myfilename, basestring):
                myfilename = myfilename.tostring()
            mypath = os.path.join(self.STORE_PATH, myfilename)
            if os.path.isfile(mypath) and os.access(mypath,os.R_OK):
                try:
                    mydict['size'] = self.entropyTools.get_file_size(mypath)
                except OSError:
                    pass
            mydict['store_url'] = os.path.join(self.store_url, myfilename)
        else:
            mydata = mydict['ddata']
            if not isinstance(mydata,basestring):
                mydata = mydata.tostring()
            try:
                mydict['size'] = len(mydata)
            except:
                pass
        return mydict

    def get_ugc_vote(self, pkgkey):
        self.check_connection()
        self.execute_query("""
        SELECT avg(entropy_votes.`vote`) as avg_vote FROM entropy_votes,entropy_base WHERE 
        entropy_base.`key` = %s AND 
        entropy_base.idkey = entropy_votes.idkey""", (pkgkey,))
        data = self.fetchone() or {}
        avg_vote = data.get('avg_vote')
        if not avg_vote:
            return 0.0
        return avg_vote

    def get_ugc_allvotes(self):

        # cached?
        cache_item = 'get_ugc_allvotes'
        cached = self.get_cached_result(cache_item)
        if cached != None:
            return cached

        self.check_connection()
        self.execute_query("""
        SELECT entropy_base.`key` as `vkey`,avg(entropy_votes.vote) as `avg_vote` FROM 
        entropy_votes,entropy_base WHERE 
        entropy_votes.`idkey` = entropy_base.`idkey` GROUP BY entropy_base.`key`""")
        vote_data = dict( ((x['vkey'], x['avg_vote'],) for x in self.fetchall()) )

        # do cache
        self.cache_result(cache_item, vote_data)
        return vote_data

    def get_ugc_downloads(self, pkgkey):
        self.check_connection()

        self.execute_query("""
        SELECT SQL_CACHE sum(entropy_downloads.`count`) as `tot_downloads` FROM 
        entropy_downloads,entropy_base WHERE entropy_base.key = %s AND 
        entropy_base.idkey = entropy_downloads.idkey""", (pkgkey,))

        data = self.fetchone() or {}
        downloads = data.get('tot_downloads')
        if not downloads:
            return 0
        return downloads

    def get_ugc_alldownloads(self):
        # cached?
        cache_item = 'get_ugc_alldownloads'
        cached = self.get_cached_result(cache_item)
        if cached != None: return cached

        self.check_connection()
        self.execute_query("""
        SELECT SQL_CACHE entropy_base.key as vkey, tot_downloads from entropy_base,
        (SELECT  idkey as idp1, sum(entropy_downloads.`count`) AS `tot_downloads` FROM
        entropy_downloads GROUP BY entropy_downloads.`idkey`) as tmp where idkey = tmp.idp1;
        """)
        down_data = dict( ((x['vkey'], x['tot_downloads'],) for x in self.fetchall()) )

        # do cache
        self.cache_result(cache_item, down_data)
        return down_data

    def get_iddoc_userid(self, iddoc):
        self.check_connection()
        self.execute_query('SELECT `userid` FROM entropy_docs WHERE `iddoc` = %s', (iddoc,))
        data = self.fetchone() or {}
        return data.get('userid', None)

    def get_total_comments_count(self):
        self.check_connection()
        self.execute_query('SELECT count(`iddoc`) as comments FROM entropy_docs WHERE `iddoctype` = %s', (self.DOC_TYPES['comments'],))
        data = self.fetchone() or {}
        comments = data.get('comments')
        if not comments:
            return 0
        return comments

    def get_total_documents_count(self):
        self.check_connection()
        self.execute_query('SELECT count(`iddoc`) as comments FROM entropy_docs WHERE `iddoctype` != %s', (self.DOC_TYPES['comments'],))
        data = self.fetchone() or {}
        comments = data.get('comments')
        if not comments:
            return 0
        return comments

    def get_total_votes_count(self):
        self.check_connection()
        self.execute_query('SELECT count(`idvote`) as votes FROM entropy_votes')
        data = self.fetchone() or {}
        votes = data.get('votes')
        if not votes:
            return 0
        return votes

    def get_total_downloads_count(self):

        # cached?
        cache_item = 'get_total_downloads_count'
        cached = self.get_cached_result(cache_item)
        if cached != None: return cached

        self.check_connection()
        self.execute_query('SELECT SQL_CACHE sum(entropy_downloads.`count`) as downloads FROM entropy_downloads')
        data = self.fetchone() or {}
        downloads = data.get('downloads', 0)
        if not downloads:
            return 0
        result = int(downloads)

        # do cache
        self.cache_result(cache_item, result)
        return result

    def get_user_score_ranking(self, userid):
        self.check_connection()
        self.execute_query('SET @row = 0')
        self.execute_query("""
        SELECT Row, col_a FROM (SELECT @row := @row + 1 AS Row, userid AS col_a FROM 
        entropy_user_scores ORDER BY score DESC) As derived1 WHERE col_a = %s""", (userid,))
        data = self.fetchone() or {}
        ranking = data.get('Row', 0) # key can be avail but == None
        if not ranking:
            return 0
        return ranking

    def get_users_scored_count(self):

        # cached?
        cache_item = 'get_users_scored_count'
        cached = self.get_cached_result(cache_item)
        if cached != None:
            return cached

        self.check_connection()
        self.execute_query('SELECT SQL_CACHE count(`userid`) as mycount FROM entropy_user_scores')
        data = self.fetchone() or {}
        count = data.get('mycount', 0)
        if not count:
            return 0

        # do cache
        self.cache_result(cache_item, count)
        return count

    def is_user_score_available(self, userid):
        self.check_connection()
        rows = self.execute_query('SELECT `userid` FROM entropy_user_scores WHERE `userid` = %s', (userid,))
        if rows:
            return True
        return False

    def calculate_user_score(self, userid):
        comments = self.get_user_comments_count(userid)
        docs = self.get_user_docs_count(userid)
        votes = self.get_user_votes_count(userid)
        return (comments*self.COMMENTS_SCORE_WEIGHT) + \
            (docs*self.DOCS_SCORE_WEIGHT) + \
            (votes*self.VOTES_SCORE_WEIGHT)

    def update_user_score(self, userid):
        self.check_connection()
        avail = self.is_user_score_available(userid)
        myscore = self.calculate_user_score(userid)
        if avail:
            self.execute_query('UPDATE entropy_user_scores SET score = %s WHERE `userid` = %s', (myscore,userid,))
        else:
            self.execute_query('INSERT INTO entropy_user_scores VALUES (%s,%s)', (userid,myscore,))
        return myscore

    def get_user_score(self, userid):
        self.check_connection()
        self.execute_query('SELECT score FROM entropy_user_scores WHERE userid = %s',(userid,))
        data = self.fetchone() or {}
        myscore = data.get('score')
        if myscore == None:
            myscore = self.update_user_score(userid)
        return myscore

    def get_users_score_ranking(self, offset = 0, count = 0):
        self.check_connection()
        limit_string = ''
        if count:
            limit_string += ' LIMIT %s,%s' % (offset,count,)
        self.execute_query('SELECT SQL_CALC_FOUND_ROWS *, userid, score FROM entropy_user_scores ORDER BY score DESC' + limit_string)
        data = self.fetchall()

        self.execute_query('SELECT FOUND_ROWS() as count')
        rdata = self.fetchone() or {}
        found_rows = rdata.get('count', 0)
        if found_rows is None:
            found_rows = 0

        return found_rows, data

    def get_user_votes_average(self, userid):
        self.check_connection()
        self.execute_query('SELECT avg(`vote`) as vote_avg FROM entropy_votes WHERE `userid` = %s', (userid,))
        data = self.fetchone() or {}
        vote_avg = data.get('vote_avg', 0.0)
        if not vote_avg:
            return 0.0
        return round(float(vote_avg), 2)

    def get_user_alldocs(self, userid):
        self.check_connection()
        self.execute_query("""
        SELECT * FROM entropy_docs,entropy_base WHERE 
        entropy_docs.`userid` = %s AND 
        entropy_base.idkey = entropy_docs.idkey ORDER BY entropy_base.`key`""", (userid,))
        return self.fetchall()

    def get_user_docs(self, userid):
        return self.get_user_generic_doctype(userid, self.DOC_TYPES['comments'], doctype_sql_cmp = "!=")

    def get_user_comments(self, userid):
        return self.get_user_generic_doctype(userid, self.DOC_TYPES['comments'], doctype_sql_cmp = "=")

    def get_user_votes(self, userid):
        self.check_connection()
        self.execute_query('SELECT * FROM entropy_votes WHERE `userid` = %s', (userid,))
        return self.fetchall()

    def get_user_generic_doctype(self, userid, doctype, doctype_sql_cmp = "="):
        self.check_connection()
        self.execute_query('SELECT * FROM entropy_docs WHERE `userid` = %s AND `iddoctype` '+doctype_sql_cmp+' %s', (userid,doctype,))
        return self.fetchall()

    def get_user_generic_doctype_count(self, userid, doctype, doctype_sql_cmp = "="):
        self.check_connection()
        self.execute_query('SELECT count(`iddoc`) as docs FROM entropy_docs WHERE `userid` = %s AND `iddoctype` '+doctype_sql_cmp+' %s', (userid,doctype,))
        data = self.fetchone() or {}
        docs = data.get('docs', 0)
        if docs is None:
            docs = 0
        return docs

    def get_user_comments_count(self, userid):
        return self.get_user_generic_doctype_count(userid, self.DOC_TYPES['comments'])

    def get_user_docs_count(self, userid):
        return self.get_user_generic_doctype_count(userid, self.DOC_TYPES['comments'], doctype_sql_cmp = "!=")

    def get_user_images_count(self, userid):
        return self.get_user_generic_doctype_count(userid, self.DOC_TYPES['image'])

    def get_user_files_count(self, userid):
        return self.get_user_generic_doctype_count(userid, self.DOC_TYPES['generic_file'])

    def get_user_yt_videos_count(self, userid):
        return self.get_user_generic_doctype_count(userid, self.DOC_TYPES['youtube_video'])

    def get_user_votes_count(self, userid):
        self.check_connection()
        self.execute_query('SELECT count(`idvote`) as votes FROM entropy_votes WHERE `userid` = %s', (userid,))
        data = self.fetchone() or {}
        votes = data.get('votes', 0)
        if votes is None:
            votes = 0
        return votes

    def get_user_stats(self, userid):
        mydict = {}
        mydict['comments'] = self.get_user_comments_count(userid)
        mydict['docs'] = self.get_user_docs_count(userid)
        mydict['images'] = self.get_user_images_count(userid)
        mydict['files'] = self.get_user_files_count(userid)
        mydict['yt_videos'] = self.get_user_yt_videos_count(userid)
        mydict['votes'] = self.get_user_votes_count(userid)
        mydict['votes_avg'] = self.get_user_votes_average(userid)
        mydict['total_docs'] = mydict['comments'] + mydict['docs']
        mydict['score'] = self.get_user_score(userid)
        mydict['ranking'] = self.get_user_score_ranking(userid)
        return mydict

    def get_distribution_stats(self):
        self.check_connection()
        mydict = {}
        mydict['comments'] = self.get_total_comments_count()
        mydict['documents'] = self.get_total_documents_count()
        mydict['votes'] = self.get_total_votes_count()
        mydict['downloads'] = self.get_total_downloads_count()
        return mydict

    def search_pkgkey_items(self, pkgkey_string, iddoctypes = None, results_offset = 0, results_limit = 30, order_by = None):
        self.check_connection()

        if iddoctypes is None:
            iddoctypes = self.DOC_TYPES.values()
        iddoctypes_str = "("+', '.join([str(x) for x in iddoctypes])+")"

        myterm = "%"+pkgkey_string+"%"

        search_params = [myterm,results_offset,results_limit]

        order_by_string = ''
        if order_by == "key":
            order_by_string = 'ORDER BY entropy_base.`key`'
        elif order_by == "username":
            order_by_string = 'ORDER BY entropy_docs.`username`'
        elif order_by == "vote":
            order_by_string = 'ORDER BY avg_vote DESC'
        elif order_by == "downloads":
            order_by_string = 'ORDER BY tot_downloads DESC'

        self.execute_query("""
        SELECT
            SQL_CALC_FOUND_ROWS entropy_base.`key`,
            entropy_docs.*,
            entropy_downloads.iddownload,
            entropy_downloads.ddate,
            entropy_votes.idvote,
            entropy_votes.vdate,
            entropy_votes.vote,
            avg(entropy_votes.vote) as avg_vote, 
            sum(entropy_downloads.`count`) as tot_downloads, 
            entropy_user_scores.score as `score`
        FROM 
            entropy_base
        LEFT JOIN entropy_votes ON entropy_base.idkey = entropy_votes.idkey
        LEFT JOIN entropy_docs ON entropy_base.idkey = entropy_docs.idkey
        LEFT JOIN entropy_docs as ed ON entropy_base.idkey = ed.idkey
        LEFT JOIN entropy_user_scores on entropy_docs.userid = entropy_user_scores.userid
        LEFT JOIN entropy_downloads on entropy_base.idkey = entropy_downloads.idkey
        WHERE 
            entropy_base.`key` LIKE %s AND
            entropy_docs.iddoctype IN """+iddoctypes_str+""" 
            GROUP BY entropy_docs.`iddoc`
            """+order_by_string+"""
            LIMIT %s,%s
        """, search_params)

        results = self.fetchall()
        for item in results:
            if item['avg_vote'] is None:
                item['avg_vote'] = 0.0

        self.execute_query('SELECT FOUND_ROWS() as count')
        data = self.fetchone() or {}
        count = data.get('count', 0)
        if count is None:
            count = 0
        return results, count

    def search_username_items(self, pkgkey_string, iddoctypes = None, results_offset = 0, results_limit = 30, order_by = None):
        self.check_connection()

        if iddoctypes is None:
            iddoctypes = self.DOC_TYPES.values()
        iddoctypes_str = "("+', '.join([str(x) for x in iddoctypes])+")"
        myterm = "%"+pkgkey_string+"%"

        search_params = [myterm,results_offset,results_limit]

        order_by_string = ''
        if order_by == "key":
            order_by_string = 'ORDER BY entropy_base.`key`'
        elif order_by == "username":
            order_by_string = 'ORDER BY entropy_docs.`username`'
        elif order_by == "vote":
            order_by_string = 'ORDER BY avg_vote DESC'
        elif order_by == "downloads":
            order_by_string = 'ORDER BY tot_downloads DESC'

        self.execute_query("""
        SELECT
            SQL_CALC_FOUND_ROWS entropy_base.`key`,
            entropy_docs.*,
            entropy_downloads.iddownload,
            entropy_downloads.ddate,
            entropy_votes.idvote,
            entropy_votes.vdate,
            entropy_votes.vote,
            avg(entropy_votes.vote) as avg_vote, 
            sum(entropy_downloads.`count`) as tot_downloads, 
            entropy_user_scores.score as `score`
        FROM 
            entropy_base
        LEFT JOIN entropy_votes ON entropy_base.idkey = entropy_votes.idkey
        LEFT JOIN entropy_docs ON entropy_base.idkey = entropy_docs.idkey
        LEFT JOIN entropy_docs as ed ON entropy_base.idkey = ed.idkey
        LEFT JOIN entropy_user_scores on entropy_docs.userid = entropy_user_scores.userid
        LEFT JOIN entropy_downloads on entropy_base.idkey = entropy_downloads.idkey
        WHERE 
            entropy_docs.`username` LIKE %s AND
            entropy_docs.iddoctype IN """+iddoctypes_str+""" 
            GROUP BY entropy_docs.`iddoc`
            """+order_by_string+"""
            LIMIT %s,%s
        """, search_params)

        results = self.fetchall()
        # avg_vote can be POTENTIALLY None, we need to change it to float(0.0)
        for item in results:
            if item['avg_vote'] is None:
                item['avg_vote'] = 0.0

        self.execute_query('SELECT FOUND_ROWS() as count')
        data = self.fetchone() or {}
        count = data.get('count', 0)
        if count is None:
            count = 0
        return results, count

    def search_content_items(self, pkgkey_string, iddoctypes = None, results_offset = 0, results_limit = 30, order_by = None):
        self.check_connection()

        if iddoctypes is None:
            iddoctypes = self.DOC_TYPES.values()
        iddoctypes_str = "("+', '.join([str(x) for x in iddoctypes])+")"
        myterm = "%"+pkgkey_string+"%"
        search_params = [myterm,myterm,myterm,results_offset,results_limit]

        order_by_string = ''
        if order_by == "key":
            order_by_string = 'ORDER BY entropy_base.`key`'
        elif order_by == "username":
            order_by_string = 'ORDER BY entropy_docs.`username`'
        elif order_by == "vote":
            order_by_string = 'ORDER BY avg_vote DESC'
        elif order_by == "downloads":
            order_by_string = 'ORDER BY tot_downloads DESC'

        self.execute_query("""
        SELECT
            SQL_CALC_FOUND_ROWS entropy_base.`key`,
            entropy_docs.*,
            entropy_downloads.iddownload,
            entropy_downloads.ddate,
            entropy_votes.idvote,
            entropy_votes.vdate,
            entropy_votes.vote,
            avg(entropy_votes.vote) as avg_vote, 
            sum(entropy_downloads.`count`) as tot_downloads, 
            entropy_user_scores.score as `score`
        FROM 
            entropy_base
        LEFT JOIN entropy_votes ON entropy_base.idkey = entropy_votes.idkey
        LEFT JOIN entropy_docs ON entropy_base.idkey = entropy_docs.idkey
        LEFT JOIN entropy_docs as ed ON entropy_base.idkey = ed.idkey
        LEFT JOIN entropy_user_scores on entropy_docs.userid = entropy_user_scores.userid
        LEFT JOIN entropy_downloads on entropy_base.idkey = entropy_downloads.idkey
        WHERE 
            (entropy_docs.`title` LIKE %s OR entropy_docs.`description` LIKE %s OR entropy_docs.`ddata` LIKE %s) AND
            entropy_docs.iddoctype IN """+iddoctypes_str+"""
            GROUP BY entropy_docs.`iddoc`
            """+order_by_string+"""
            LIMIT %s,%s
        """, search_params)

        results = self.fetchall()
        # avg_vote can be POTENTIALLY None, we need to change it to float(0.0)
        for item in results:
            if item['avg_vote'] is None:
                item['avg_vote'] = 0.0

        self.execute_query('SELECT FOUND_ROWS() as count')
        data = self.fetchone() or {}
        count = data.get('count', 0)
        if count is None:
            count = 0
        return results, count

    def search_keyword_items(self, keyword_string, iddoctypes = None, results_offset = 0, results_limit = 30, order_by = None):
        self.check_connection()

        if iddoctypes is None:
            iddoctypes = self.DOC_TYPES.values()
        iddoctypes_str = "("+', '.join([str(x) for x in iddoctypes])+")"
        myterm = "%"+keyword_string+"%"

        search_params = [myterm,results_offset,results_limit]

        order_by_string = ''
        if order_by == "key":
            order_by_string = 'ORDER BY entropy_base.`key`'
        elif order_by == "username":
            order_by_string = 'ORDER BY entropy_docs.`username`'
        elif order_by == "vote":
            order_by_string = 'ORDER BY avg_vote DESC'
        elif order_by == "downloads":
            order_by_string = 'ORDER BY tot_downloads DESC'

        self.execute_query("""
        SELECT
            SQL_CALC_FOUND_ROWS entropy_base.`key`,
            entropy_docs.*,
            entropy_downloads.iddownload,
            entropy_downloads.ddate,
            entropy_votes.idvote,
            entropy_votes.vdate,
            entropy_votes.vote,
            avg(entropy_votes.vote) as avg_vote, 
            sum(entropy_downloads.`count`) as tot_downloads, 
            entropy_user_scores.score as `score`
        FROM 
            entropy_base
        LEFT JOIN entropy_votes ON entropy_base.idkey = entropy_votes.idkey
        LEFT JOIN entropy_docs ON entropy_base.idkey = entropy_docs.idkey
        LEFT JOIN entropy_docs as ed ON entropy_base.idkey = ed.idkey
        LEFT JOIN entropy_user_scores on entropy_docs.userid = entropy_user_scores.userid
        LEFT JOIN entropy_downloads on entropy_base.idkey = entropy_downloads.idkey
        WHERE 
            entropy_docs_keywords.`keyword` LIKE %s AND 
            entropy_docs.iddoctype IN """+iddoctypes_str+"""
            GROUP BY entropy_docs.`iddoc`
            """+order_by_string+"""
            LIMIT %s,%s
        """, search_params)

        results = self.fetchall()
        # avg_vote can be POTENTIALLY None, we need to change it to float(0.0)
        for item in results:
            if item['avg_vote'] is None:
                item['avg_vote'] = 0.0

        self.execute_query('SELECT FOUND_ROWS() as count')
        data = self.fetchone() or {}
        count = data.get('count', 0)
        if count is None:
            count = 0
        return results, count

    def search_iddoc_item(self, iddoc_string, iddoctypes = None, results_offset = 0, results_limit = 30, order_by = None):
        self.check_connection()

        if iddoctypes is None:
            iddoctypes = self.DOC_TYPES.values()
        iddoctypes_str = "("+', '.join([str(x) for x in iddoctypes])+")"
        try:
            myterm = int(iddoc_string)
        except ValueError:
            return [], 0

        search_params = [myterm,results_offset,results_limit]

        order_by_string = ''
        if order_by == "key":
            order_by_string = 'ORDER BY entropy_base.`key`'
        elif order_by == "username":
            order_by_string = 'ORDER BY entropy_docs.`username`'
        elif order_by == "vote":
            order_by_string = 'ORDER BY avg_vote DESC'
        elif order_by == "downloads":
            order_by_string = 'ORDER BY tot_downloads DESC'

        self.execute_query("""
        SELECT SQL_CALC_FOUND_ROWS *, avg(entropy_votes.`vote`) as avg_vote, 
        sum(entropy_downloads.`count`) as `tot_downloads`, 
        entropy_user_scores.`score` as `score` FROM 
        entropy_docs,entropy_base,entropy_votes,entropy_downloads,entropy_user_scores WHERE 
        entropy_docs.`iddoc` = %s AND 
        entropy_docs.`iddoctype` IN """+iddoctypes_str+""" AND 
        entropy_docs.`idkey` = entropy_base.`idkey` AND 
        entropy_votes.`idkey` = entropy_base.`idkey` AND 
        entropy_downloads.`idkey` = entropy_base.`idkey` AND 
        entropy_docs.`userid` = entropy_user_scores.`userid` 
        GROUP BY entropy_docs.`iddoc` """+order_by_string+""" LIMIT %s,%s""", search_params)

        results = self.fetchall()
        # avg_vote can be POTENTIALLY None, we need to change it to float(0.0)
        for item in results:
            if item['avg_vote'] is None:
                item['avg_vote'] = 0.0

        self.execute_query('SELECT FOUND_ROWS() as count')
        data = self.fetchone() or {}
        count = data.get('count', 0)
        if count is None:
            count = 0
        return results, count

    def handle_pkgkey(self, key):
        idkey = self.get_idkey(key)
        if idkey == -1:
            return self.insert_pkgkey(key)
        return idkey

    def insert_flood_control_check(self, userid):
        self.check_connection()
        self.execute_query('SELECT max(`ts`) as ts FROM entropy_docs WHERE `userid` = %s', (userid,))
        data = self.fetchone()
        if not data:
            return False
        elif not data.has_key('ts'):
            return False
        elif data['ts'] == None:
            return False
        delta = self.datetime.fromtimestamp(time.time()) - data['ts']
        if (delta.days == 0) and (delta.seconds <= self.FLOOD_INTERVAL):
            return True
        return False

    def insert_generic_doc(self, idkey, userid, username, doc_type, data, title, description, keywords, do_commit = False):
        self.check_connection()

        title = title[:self.entropy_docs_title_len]
        description = description[:self.entropy_docs_description_len]

        # flood control
        flood_risk = self.insert_flood_control_check(userid)
        if flood_risk:
            return 'flooding detected'

        self.execute_query('INSERT INTO entropy_docs VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',(
                None,
                idkey,
                userid,
                username,
                doc_type,
                data,
                title,
                description,
                None,
            )
        )
        if do_commit:
            self.commit()
        iddoc = self.lastrowid()
        self.insert_keywords(iddoc, keywords)
        self.update_user_score(userid)
        return iddoc

    def insert_keywords(self, iddoc, keywords):
        keywords = keywords.split(",")
        clean_keys = []
        for key in keywords:
            try:
                key = key.strip().split()[0]
            except IndexError:
                continue
            if not key: continue
            if not key.isalnum(): continue
            key = key[:self.entropy_docs_keyword_len]
            if key in clean_keys: continue
            clean_keys.append(key)

        if not clean_keys:
            return

        mydata = []
        for key in clean_keys:
            mydata.append((iddoc, key,))

        self.execute_many('INSERT INTO entropy_docs_keywords VALUES (%s,%s)', mydata)

    def remove_keywords(self, iddoc):
        self.execute_query('DELETE FROM entropy_docs_keywords WHERE `iddoc` = %s',(iddoc,))

    def insert_comment(self, pkgkey, userid, username, comment, title, keywords, do_commit = False):
        self.check_connection()
        idkey = self.handle_pkgkey(pkgkey)
        iddoc = self.insert_generic_doc(idkey, userid, username,
            self.DOC_TYPES['comments'], comment, title, '', keywords)
        if isinstance(iddoc, basestring):
            return False, iddoc
        if do_commit:
            self.commit()
        return True, iddoc

    def edit_comment(self, iddoc, new_comment, new_title, new_keywords, do_commit = False):
        self.check_connection()
        if not self.is_iddoc_available(iddoc):
            return False
        new_title = new_title[:self.entropy_docs_title_len]
        self.execute_query('UPDATE entropy_docs SET `ddata` = %s, `title` = %s WHERE `iddoc` = %s AND `iddoctype` = %s',(
                new_comment,
                new_title,
                iddoc,
                self.DOC_TYPES['comments'],
            )
        )
        self.remove_keywords(iddoc)
        self.insert_keywords(iddoc, new_keywords)
        if do_commit:
            self.commit()
        return True, iddoc

    def remove_comment(self, iddoc):
        self.check_connection()
        userid = self.get_iddoc_userid(iddoc)
        self.remove_keywords(iddoc)
        self.execute_query('DELETE FROM entropy_docs WHERE `iddoc` = %s AND `iddoctype` = %s',(
                iddoc,
                self.DOC_TYPES['comments'],
            )
        )
        if userid:
            self.update_user_score(userid)
        return True, iddoc

    # give a vote to an app
    def do_vote(self, pkgkey, userid, vote, do_commit = False):
        self.check_connection()
        idkey = self.handle_pkgkey(pkgkey)
        vote = int(vote)
        if vote not in self.VOTE_RANGE: # weird
            vote = 3 # avg?
        mydate = self.get_date()
        if self.has_user_already_voted(pkgkey, userid):
            return False
        self.execute_query('INSERT INTO entropy_votes VALUES (%s,%s,%s,%s,%s,%s)',(
                None,
                idkey,
                userid,
                mydate,
                vote,
                None,
            )
        )
        if do_commit:
            self.commit()
        self.update_user_score(userid)
        return True

    def has_user_already_voted(self, pkgkey, userid):
        self.check_connection()
        idkey = self.handle_pkgkey(pkgkey)
        self.execute_query('SELECT `idvote` FROM entropy_votes WHERE `idkey` = %s AND `userid` = %s', (idkey,userid,))
        data = self.fetchone()
        if data:
            return True
        return False

    # icrement +1 download usage for the provided package keys
    def do_downloads(self, pkgkeys, ip_addr = None, do_commit = False):
        self.check_connection()
        mydate = self.get_date()
        iddownloads = set()
        for pkgkey in pkgkeys:
            iddownload = self.get_iddownload(pkgkey, mydate)
            if iddownload == -1:
                iddownload = self.insert_download(pkgkey, mydate, count = 1)
            else:
                self.update_download(iddownload)
            if (iddownload > 0) and isinstance(ip_addr,basestring):
                iddownloads.add(iddownload)

        if iddownloads:
            self.store_download_data(iddownloads, ip_addr)
        if do_commit:
            self.commit()
        return True

    def do_download_stats(self, branch, release_string, hw_hash, pkgkeys,
        ip_addr, do_commit = False):

        self.check_connection()
        branch_id = self.get_entropy_branches_id(branch)
        if branch_id == -1:
            branch_id = self.insert_entropy_branch(branch)

        rel_strings_id = self.get_entropy_release_strings_id(release_string)
        if rel_strings_id == -1:
            rel_strings_id = self.insert_entropy_release_string(release_string)

        self.do_downloads(pkgkeys, ip_addr = ip_addr)

        entropy_distribution_usage_id = self.is_user_ip_available_in_entropy_distribution_usage(ip_addr)

        hits = 1
        if self.STATS_MAP['installer'] in pkgkeys:
            hits = 0
        if entropy_distribution_usage_id == -1:
            entropy_ip_locations_id = self.handle_entropy_ip_locations_id(ip_addr)
            self.execute_query('INSERT INTO entropy_distribution_usage VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',(
                    None,
                    branch_id,
                    rel_strings_id,
                    None,
                    ip_addr,
                    entropy_ip_locations_id,
                    self.get_datetime(),
                    hits,
                )
            )
            entropy_distribution_usage_id = self.lastrowid()
        else:
            self.execute_query("""
            UPDATE entropy_distribution_usage SET `entropy_branches_id` = %s, 
            `entropy_release_strings_id` = %s, 
            `hits` = `hits`+%s 
            WHERE `entropy_distribution_usage_id` = %s
            """,(
                    branch_id,
                    rel_strings_id,
                    hits,
                    entropy_distribution_usage_id,
                )
            )

        # store hardware hash if set
        if hw_hash and not \
            self.is_entropy_hardware_usage_stats_available(entropy_distribution_usage_id):

            self.do_entropy_hardware_usage_stats(entropy_distribution_usage_id,
                hw_hash)

        if do_commit: self.commit()
        return True

    def do_entropy_hardware_usage_stats(self, entropy_distribution_usage_id, hw_hash):

        self.execute_query('INSERT INTO entropy_hardware_usage VALUES (%s,%s,%s)', (
                None,
                entropy_distribution_usage_id,
                hw_hash,
            )
        )

    def is_entropy_hardware_usage_stats_available(self, entropy_distribution_usage_id):
        self.check_connection()
        self.execute_query('SELECT entropy_hardware_usage_id  FROM entropy_hardware_usage WHERE `entropy_distribution_usage_id` = %s',(entropy_distribution_usage_id,))
        data = self.fetchone()
        if data:
            return True
        return False

    def is_user_ip_available_in_entropy_distribution_usage(self, ip_address):
        self.check_connection()
        self.execute_query('SELECT entropy_distribution_usage_id FROM entropy_distribution_usage WHERE `ip_address` = %s',(ip_address,))
        data = self.fetchone() or {}
        myid = data.get('entropy_distribution_usage_id')
        if myid is None:
            return -1
        return myid

    def insert_document(self, pkgkey, userid, username, text, title,
            description, keywords, doc_type = None, do_commit = False):
        self.check_connection()
        idkey = self.handle_pkgkey(pkgkey)
        if doc_type == None: doc_type = self.DOC_TYPES['bbcode_doc']
        iddoc = self.insert_generic_doc(idkey, userid, username, doc_type,
            text, title, description, keywords)
        if isinstance(iddoc, basestring):
            return False, iddoc
        if do_commit:
            self.commit()
        return True, iddoc

    def edit_document(self, iddoc, new_document, new_title, new_keywords, do_commit = False):
        self.check_connection()
        if not self.is_iddoc_available(iddoc):
            return False

        new_title = new_title[:self.entropy_docs_title_len]

        self.execute_query('UPDATE entropy_docs SET `ddata` = %s, `title` = %s  WHERE `iddoc` = %s AND `iddoctype` = %s',(
                new_document,
                new_title,
                iddoc,
                self.DOC_TYPES['bbcode_doc'],
            )
        )
        self.remove_keywords(iddoc)
        self.insert_keywords(iddoc, new_keywords)
        if do_commit:
            self.commit()
        return True, iddoc

    def remove_document(self, iddoc):
        self.check_connection()
        userid = self.get_iddoc_userid(iddoc)
        self.remove_keywords(iddoc)
        self.execute_query('DELETE FROM entropy_docs WHERE `iddoc` = %s AND `iddoctype` = %s',(
                iddoc,
                self.DOC_TYPES['bbcode_doc'],
            )
        )
        if userid:
            self.update_user_score(userid)
        return True, iddoc

    def scan_for_viruses(self, filepath):

        if not os.access(filepath,os.R_OK):
            return False,None

        args = [self.VIRUS_CHECK_EXEC]
        args += self.VIRUS_CHECK_ARGS
        args += [filepath]
        f = open("/dev/null","w")
        p = subprocess.Popen(args, stdout = f, stderr = f)
        rc = p.wait()
        f.close()
        if rc == 1:
            return True, None
        return False, None

    def insert_generic_file(self, pkgkey, userid, username, file_path,
            file_name, doc_type, title, description, keywords):
        self.check_connection()
        file_path = os.path.realpath(file_path)

        # do a virus check?
        virus_found, virus_type = self.scan_for_viruses(file_path)
        if virus_found:
            os.remove(file_path)
            return False, None

        # flood control
        flood_risk = self.insert_flood_control_check(userid)
        if flood_risk: return False, 'flooding detected'

        # validity check
        if doc_type == self.DOC_TYPES['image']:
            valid = False
            if os.path.isfile(file_path) and os.access(file_path,os.R_OK):
                valid = self.entropyTools.is_supported_image_file(file_path)
            if not valid:
                return False, 'not a valid image'

        dest_path = os.path.join(self.STORE_PATH,file_name)

        # create dir if not exists
        dest_dir = os.path.dirname(dest_path)
        if not os.path.isdir(dest_dir):
            try:
                os.makedirs(dest_dir)
            except OSError, e:
                raise PermissionDenied('PermissionDenied: %s' % (e,))
            if etpConst['entropygid'] != None:
                const_setup_perms(dest_dir,etpConst['entropygid'])

        orig_dest_path = dest_path
        dcount = 0
        while os.path.isfile(dest_path):
            dcount += 1
            dest_path_name = "%s_%s" % (dcount,os.path.basename(orig_dest_path),)
            dest_path = os.path.join(os.path.dirname(orig_dest_path),dest_path_name)

        if os.path.dirname(file_path) != dest_dir:
            try:
                os.rename(file_path, dest_path)
            except OSError:
                # fallback to non atomic
                shutil.move(file_path, dest_path)
        if etpConst['entropygid'] != None:
            try:
                const_setup_file(dest_path, etpConst['entropygid'], 0664)
            except OSError:
                pass
            # at least set chmod
            try:
                const_set_chmod(dest_path,0664)
            except OSError:
                pass

        title = title[:self.entropy_docs_title_len]
        description = description[:self.entropy_docs_description_len]

        # now store in db
        idkey = self.handle_pkgkey(pkgkey)
        self.execute_query('INSERT INTO entropy_docs VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',(
                None,
                idkey,
                userid,
                username,
                doc_type,
                file_name,
                title,
                description,
                None,
            )
        )
        iddoc = self.lastrowid()
        self.insert_keywords(iddoc, keywords)
        store_url = os.path.basename(dest_path)
        if self.store_url:
            store_url = os.path.join(self.store_url,store_url)
        self.update_user_score(userid)
        return True, (iddoc, store_url)

    def insert_image(self, pkgkey, userid, username, image_path, file_name,
            title, description, keywords):
        return self.insert_generic_file(pkgkey, userid, username, image_path,
            file_name, self.DOC_TYPES['image'], title, description, keywords)

    def insert_file(self, pkgkey, userid, username, file_path, file_name, title,
            description, keywords):
        return self.insert_generic_file(pkgkey, userid, username, file_path,
            file_name, self.DOC_TYPES['generic_file'], title, description,
            keywords)

    def delete_image(self, iddoc):
        return self.delete_generic_file(iddoc, self.DOC_TYPES['image'])

    def delete_file(self, iddoc):
        return self.delete_generic_file(iddoc, self.DOC_TYPES['generic_file'])

    def delete_generic_file(self, iddoc, doc_type):
        self.check_connection()

        userid = self.get_iddoc_userid(iddoc)
        self.execute_query('SELECT `ddata` FROM entropy_docs WHERE `iddoc` = %s AND `iddoctype` = %s',(
                iddoc,
                doc_type,
            )
        )
        data = self.fetchone() or {}
        mypath = data.get('ddata')
        if not isinstance(mypath, basestring) and (mypath is not None):
            mypath = mypath.tostring()
        if mypath is not None:
            mypath = os.path.join(self.STORE_PATH,mypath)
            if os.path.isfile(mypath) and os.access(mypath,os.W_OK):
                os.remove(mypath)

        self.remove_keywords(iddoc)
        self.execute_query('DELETE FROM entropy_docs WHERE `iddoc` = %s AND `iddoctype` = %s',(
                iddoc,
                doc_type,
            )
        )
        if userid:
            self.update_user_score(userid)
        return True, (iddoc, None)

    def insert_youtube_video(self, pkgkey, userid, username, video_path, file_name, title, description, keywords):
        self.check_connection()
        if not self.gdata:
            return False, None

        idkey = self.handle_pkgkey(pkgkey)
        video_path = os.path.realpath(video_path)
        if not (os.access(video_path,os.R_OK) and os.path.isfile(video_path)):
            return False
        virus_found, virus_type = self.scan_for_viruses(video_path)
        if virus_found:
            os.remove(video_path)
            return False, None

        new_video_path = video_path
        if isinstance(file_name,basestring):
            # move file to the new filename
            new_video_path = os.path.join(os.path.dirname(video_path),os.path.basename(file_name)) # force basename
            scount = 0
            while os.path.lexists(new_video_path):
                scount += 1
                bpath = "%s.%s" % (unicode(scount),os.path.basename(file_name),)
                new_video_path = os.path.join(os.path.dirname(video_path),bpath)
            shutil.move(video_path,new_video_path)

        yt_service = self.get_youtube_service()
        if yt_service == None:
            return False, None

        mykeywords = ', '.join([x.strip().strip(',') for x in \
            keywords.split() + ["sabayon"] if (x.strip() and x.strip(",") and \
                (len(x.strip()) > 4))])
        gd_keywords = self.gdata.media.Keywords(text = mykeywords)

        mydescription = "%s: %s" % (pkgkey,description,)
        mytitle = "%s: %s" % (self.system_name,title,)
        my_media_group = self.gdata.media.Group(
            title = self.gdata.media.Title(text = mytitle),
            description = self.gdata.media.Description(
                description_type = 'plain',
                text = mydescription
            ),
            keywords = gd_keywords,
            category = self.gdata.media.Category(
                text = 'Tech',
                scheme = 'http://gdata.youtube.com/schemas/2007/categories.cat',
                label = 'Tech'
            ),
            player = None
        )
        video_entry = self.gdata.youtube.YouTubeVideoEntry(media = my_media_group)
        new_entry = yt_service.InsertVideoEntry(video_entry, new_video_path)
        if not isinstance(new_entry, self.gdata.youtube.YouTubeVideoEntry):
            return False, None
        video_url = new_entry.GetSwfUrl()
        video_id = os.path.basename(video_url)

        iddoc = self.insert_generic_doc(idkey, userid, username,
            self.DOC_TYPES['youtube_video'], video_id, title, description,
            keywords)
        if isinstance(iddoc,basestring):
            return False, (iddoc, None,)
        return True, (iddoc, video_id,)

    def remove_youtube_video(self, iddoc):
        self.check_connection()
        if not self.gdata:
            return False, None
        if not self.is_iddoc_available(iddoc):
            return False, None
        userid = self.get_iddoc_userid(iddoc)

        yt_service = self.get_youtube_service()
        if yt_service == None:
            return False, None

        def do_remove():
            self.remove_keywords(iddoc)
            self.execute_query('DELETE FROM entropy_docs WHERE `iddoc` = %s AND `iddoctype` = %s',(
                    iddoc,
                    self.DOC_TYPES['youtube_video'],
                )
            )

        self.execute_query('SELECT `ddata` FROM entropy_docs WHERE `iddoc` = %s AND `iddoctype` = %s',(
                iddoc,
                self.DOC_TYPES['youtube_video'],
            )
        )
        data = self.fetchone()
        if data is None:
            do_remove()
            return False, None
        elif not data.has_key('ddata'):
            do_remove()
            return False, None

        video_id = data.get('ddata')
        try:
            video_entry = yt_service.GetYouTubeVideoEntry(video_id = video_id)
            deleted = yt_service.DeleteVideoEntry(video_entry)
        except:
            deleted = True

        if deleted:
            do_remove()
        if userid: self.update_user_score(userid)
        return deleted, (iddoc, video_id,)

    def get_youtube_service(self):
        self.check_connection()
        if not self.gdata:
            return None
        keywords = ['google_email', 'google_password']
        for keyword in keywords:
            if not self.connection_data.has_key(keyword):
                return None
        # note: your google account must be linked with the YouTube one
        srv = self.YouTubeService.YouTubeService()
        srv.email = self.connection_data['google_email']
        srv.password = self.connection_data['google_password']
        if self.connection_data.has_key('google_developer_key'):
            srv.developer_key = self.connection_data['google_developer_key']
        if self.connection_data.has_key('google_client_id'):
            srv.client_id = self.connection_data['google_client_id']
        srv.source = 'Entropy'
        srv.ProgrammaticLogin()
        return srv

class Client:

    import socket
    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    import zlib
    import select
    def __init__(self, OutputInterface, ClientCommandsClass, quiet = False, show_progress = True, output_header = '', ssl = False, socket_timeout = 25):
        #, server_ca_cert = None, server_cert = None):

        if not hasattr(OutputInterface,'updateProgress'):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (OutputInterface,mytxt,))
        elif not callable(OutputInterface.updateProgress):
            mytxt = _("OutputInterface does not have an updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (OutputInterface,mytxt,))

        from entropy.client.services.ugc.commands import Base
        if not issubclass(ClientCommandsClass, (Base,)):
            mytxt = _("A valid entropy.client.services.ugc.commands.Base interface is needed")
            raise IncorrectParameter("IncorrectParameter: %s, (! %s !)" % (ClientCommandsClass,mytxt,))

        self.ssl_mod = None
        self.setup_ssl(ssl) #, server_ca_cert, server_cert)

        self.answers = etpConst['socket_service']['answers']
        self.Output = OutputInterface
        self.sock_conn = None
        self.real_sock_conn = None
        self.hostname = None
        self.hostport = None
        self.buffered_data = ''
        self.buffer_length = None
        self.quiet = quiet
        self.show_progress = show_progress
        self.output_header = output_header
        self.CmdInterface = ClientCommandsClass(self.Output, self)
        self.CmdInterface.output_header = self.output_header
        self.socket_timeout = socket_timeout
        self.socket.setdefaulttimeout(self.socket_timeout)


    def setup_ssl(self, ssl): # , server_ca_cert, server_cert):
        # SSL Support
        self.SSL = {}
        self.SSL_exceptions = {
            'WantReadError': None,
            'WantWriteError': None,
            'WantX509LookupError': None,
            'ZeroReturnError': None,
            'Error': None,
            'SysCallError': None
        }
        self.ssl = ssl
        self.pyopenssl = True
        self.context = None

        '''
            self.server_cert = server_cert
            self.server_ca_cert = server_ca_cert
            self.ssl_pkey = None
            self.ssl_cert = None
            self.ssl_CN = 'Entropy Repository Service Client'
            self.ssl_digest = 'md5'
            self.ssl_serial = 1
            self.ssl_not_before = 0
            self.ssl_not_after = 60*60*24*1 # 1 day
        '''

        if self.ssl:

            if "--nopyopenssl" in sys.argv:
                self.pyopenssl = False
            else:
                try:
                    from OpenSSL import SSL, crypto
                except ImportError:
                    self.pyopenssl = False

            # SSL module (Python 2.6)
            try:
                import ssl as ssl_mod
                self.ssl_mod = ssl_mod
            except ImportError:
                pass

            '''
            if not (self.server_cert and self.server_ca_cert):
                raise SSLError('SSLError: %s: %s' % (_("Specified SSL server certificate not available"),)
            if not (os.path.isfile(self.server_cert) and \
                    os.access(self.server_cert,os.R_OK) and \
                    os.path.isfile(self.server_ca_cert) and \
                    os.access(self.server_ca_cert,os.R_OK)) and self.pyopenssl:
                        raise SSLError('SSLError: %s: %s' % (_("Specified SSL server certificate not available"),self.server_cert,))
            '''

            if self.pyopenssl:

                self.SSL_exceptions['WantReadError'] = SSL.WantReadError
                self.SSL_exceptions['WantWriteError'] = SSL.WantWriteError
                self.SSL_exceptions['WantX509LookupError'] = SSL.WantX509LookupError
                self.SSL_exceptions['ZeroReturnError'] = SSL.ZeroReturnError
                self.SSL_exceptions['Error'] = SSL.Error
                self.SSL_exceptions['SysCallError'] = SSL.SysCallError
                self.SSL['m'] = SSL
                self.SSL['crypto'] = crypto

                # setup an SSL context.
                self.context = self.SSL['m'].Context(self.SSL['m'].SSLv23_METHOD)
                #self.context.set_verify(self.SSL['m'].VERIFY_PEER, self.verify_ssl_cb)

                # load up certificate stuff.
                '''
                    self.ssl_pkey = self.create_ssl_key_pair(self.SSL['crypto'].TYPE_RSA, 1024)
                    self.context.use_privatekey(self.ssl_pkey)
                    self.context.use_certificate_file(self.server_cert)
                    self.context.load_verify_locations(self.server_ca_cert)
                    self.context.load_client_ca(self.server_cert)
                    self.ssl_pkey = self.create_ssl_key_pair(self.SSL['crypto'].TYPE_RSA, 1024)
                    self.ssl_cert = self.create_ssl_certificate(self.ssl_pkey)
                    self.context.use_privatekey(self.ssl_pkey)
                    self.context.use_certificate(self.ssl_cert)
                    self.context.load_client_ca(self.server_cert)
                '''

        else:
            self.ssl = False
            self.pyopenssl = False


    def check_pyopenssl(self):
        if not self.pyopenssl:
            raise SSLError('SSLError: %s' % (_("OpenSSL Python module not available, you need dev-python/pyopenssl"),))

    '''
    # this function should do the authentication checking to see that
    # the client is who they say they are.
    def verify_ssl_cb(self, conn, cert, errnum, depth, ok):
        self.check_pyopenssl()
        #print 'Got certificate: %s' % cert.get_subject()
        #print repr(ok),repr(cert),repr(errnum),repr(depth)
        return ok


    def create_ssl_key_pair(self, keytype, bits):
        if not self.pyopenssl:
            raise SSLError('SSLError: %s' % (_("OpenSSL Python module not available, you need dev-python/pyopenssl"),))
        pkey = self.SSL['crypto'].PKey()
        pkey.generate_key(keytype, bits)
        return pkey

    def create_ssl_certificate(self, pkey):
        self.check_pyopenssl()
        myreq = self.create_ssl_certificate_request(pkey, CN = self.ssl_CN)
        cert = self.SSL['crypto'].X509()
        cert.set_serial_number(self.ssl_serial)
        cert.gmtime_adj_notBefore(self.ssl_not_before)
        cert.gmtime_adj_notAfter(self.ssl_not_after)
        cert.set_issuer(myreq.get_subject())
        cert.set_subject(myreq.get_subject())
        cert.set_pubkey(myreq.get_pubkey())
        cert.sign(pkey, self.ssl_digest)
        return cert

    def create_ssl_certificate_request(self, pkey, **name):
        self.check_pyopenssl()
        req = self.SSL['crypto'].X509Req()
        subj = req.get_subject()
        for (key,value) in name.items():
            setattr(subj, key, value)
        req.set_pubkey(pkey)
        req.sign(pkey, self.ssl_digest)

        return req
    '''

    def stream_to_object(self, data, gzipped):

        if gzipped:
            data = self.zlib.decompress(data)
        obj = self.dumpTools.unserialize_string(data)

        return obj

    def append_eos(self, data):
        return str(len(data))+self.answers['eos']+data

    def transmit(self, data):
        self.check_socket_connection()
        if hasattr(self.sock_conn,'settimeout'):
            self.sock_conn.settimeout(self.socket_timeout)
        data = self.append_eos(data)
        try:

            encode_done = False
            mydata = data[:]
            while 1:
                try:
                    if self.ssl and not self.pyopenssl:
                        sent = self.sock_conn.write(mydata)
                    else:
                        sent = self.sock_conn.send(mydata)
                    if sent == len(mydata):
                        break
                    mydata = mydata[sent:]
                except (self.SSL_exceptions['WantWriteError'],
                    self.SSL_exceptions['WantReadError'],):
                    time.sleep(0.2)
                    continue
                except UnicodeEncodeError, e:
                    if encode_done:
                        raise
                    mydata = mydata.encode('utf-8')
                    encode_done = True
                    continue

        except self.SSL_exceptions['Error'], e:
            self.disconnect()
            raise SSLError('SSLError: %s' % (e,))
        except self.socket.sslerror, e:
            self.disconnect()
            raise SSLError('SSL Socket error: %s' % (e,))
        except:
            self.disconnect()
            raise

    def close_session(self, session_id):
        self.check_socket_connection()
        try:
            self.transmit("%s end" % (session_id,))
            # since we don't know if it's expired, we need to wrap it
            data = self.receive()
        except self.socket.error, e:
            if etpUi['debug']:
                self.entropyTools.print_traceback()
                import pdb
                pdb.set_trace()
            if e[0] == 32: # broken pipe
                return None
            raise
        except SSLError:
            raise
        return data

    def open_session(self):
        self.check_socket_connection()
        self.socket.setdefaulttimeout(self.socket_timeout)
        self.transmit('begin')
        data = self.receive()
        return data

    def is_session_alive(self, session):
        self.check_socket_connection()
        self.socket.setdefaulttimeout(self.socket_timeout)
        self.transmit('alive %s' % (session,))
        data = self.receive()
        if data == self.answers['ok']:
            return True
        return False

    def receive(self):

        self.check_socket_connection()
        if hasattr(self.sock_conn,'settimeout'):
            self.sock_conn.settimeout(self.socket_timeout)
        self.ssl_prepending = True

        def do_receive():
            data = ''
            if self.ssl and not self.pyopenssl:
                data = self.sock_conn.read(1024)
            elif self.ssl:
                if self.ssl_prepending:
                    data = self.sock_conn.recv(1024)
                    self.ssl_prepending = False
                while self.sock_conn.pending():
                    data += self.sock_conn.recv(1024)
            else:
                data = self.sock_conn.recv(1024)
            return data

        myeos = self.answers['eos']
        ssl_error_loop_count = 0
        while 1:

            try:

                data = do_receive()
                if self.buffer_length == None:
                    self.buffered_data = ''
                    if (data == '') or (data == self.answers['cl']):
                        # nein! no support, KAPUTT!
                        # RAUSS!
                        if not self.quiet:
                            mytxt = _("command not supported. receive aborted")
                            self.Output.updateProgress(
                                "[%s:%s] %s" % (
                                        brown(self.hostname),
                                        bold(str(self.hostport)),
                                        blue(mytxt),
                                ),
                                importance = 1,
                                type = "warning",
                                header = self.output_header
                            )
                        return None
                    elif len(data) < len(myeos):
                        if not self.quiet:
                            mytxt = _("malformed EOS. receive aborted")
                            self.Output.updateProgress(
                                "[%s:%s] %s" % (
                                        brown(self.hostname),
                                        bold(str(self.hostport)),
                                        blue(mytxt),
                                ),
                                importance = 1,
                                type = "warning",
                                header = self.output_header
                            )
                        if etpUi['debug']:
                            self.entropyTools.print_traceback()
                            import pdb
                            pdb.set_trace()
                        return None
                    mystrlen = data.split(myeos)[0]
                    self.buffer_length = int(mystrlen)
                    data = data[len(mystrlen)+1:]
                    self.buffer_length -= len(data)
                    self.buffered_data = data
                else:
                    self.buffer_length -= len(data)
                    self.buffered_data += data

                while self.buffer_length > 0:
                    x = do_receive()
                    if self.ssl and self.pyopenssl and not x:
                        self.ssl_prepending = True
                    self.buffer_length -= len(x)
                    self.buffered_data += x
                self.buffer_length = None
                break

            except ValueError, e:
                if not self.quiet:
                    mytxt = _("malformed data. receive aborted")
                    self.Output.updateProgress(
                        "[%s:%s] %s: %s" % (
                                brown(self.hostname),
                                bold(str(self.hostport)),
                                blue(mytxt),
                                e,
                        ),
                        importance = 1,
                        type = "warning",
                        header = self.output_header
                    )
                return None
            except self.socket.timeout, e:
                if not self.quiet:
                    mytxt = _("connection timed out while receiving data")
                    self.Output.updateProgress(
                        "[%s:%s] %s: %s" % (
                                brown(self.hostname),
                                bold(str(self.hostport)),
                                blue(mytxt),
                                e,
                        ),
                        importance = 1,
                        type = "warning",
                        header = self.output_header
                    )
                return None
            except self.socket.error, e:
                if not self.quiet:
                    mytxt = _("connection error while receiving data")
                    self.Output.updateProgress(
                        "[%s:%s] %s: %s" % (
                                brown(self.hostname),
                                bold(str(self.hostport)),
                                blue(mytxt),
                                e,
                        ),
                        importance = 1,
                        type = "warning",
                        header = self.output_header
                    )
                return None
            except (self.SSL_exceptions['WantReadError'],self.SSL_exceptions['WantX509LookupError'],), e:
                ssl_error_loop_count += 1
                if ssl_error_loop_count > 3000000:
                    if not self.quiet:
                        mytxt = _("too many WantReadError error while receiving data")
                        self.Output.updateProgress(
                            "[%s:%s] %s: %s" % (
                                    brown(self.hostname),
                                    bold(str(self.hostport)),
                                    blue(mytxt),
                                    e,
                            ),
                            importance = 1,
                            type = "warning",
                            header = self.output_header
                        )
                    return None
                continue
            except self.SSL_exceptions['ZeroReturnError']:
                break
            except self.SSL_exceptions['SysCallError'], e:
                if not self.quiet:
                    mytxt = _("syscall error while receiving data")
                    self.Output.updateProgress(
                        "[%s:%s] %s: %s" % (
                                brown(self.hostname),
                                bold(str(self.hostport)),
                                blue(mytxt),
                                e,
                        ),
                        importance = 1,
                        type = "warning",
                        header = self.output_header
                    )
                return None

        return self.buffered_data

    def reconnect_socket(self):
        if not self.quiet:
            mytxt = _("Reconnecting to socket")
            self.Output.updateProgress(
                "[%s:%s] %s" % (
                        brown(unicode(self.hostname)),
                        bold(unicode(self.hostport)),
                        blue(mytxt),
                ),
                importance = 1,
                type = "info",
                header = self.output_header
            )
        self.connect(self.hostname,self.hostport)

    def check_socket_connection(self):
        if not self.sock_conn:
            raise ConnectionError("ConnectionError: %s" % (_("Not connected to host"),))

    def connect(self, host, port):

        if self.ssl:
            self.real_sock_conn = self.socket.socket(self.socket.AF_INET, self.socket.SOCK_STREAM)
            if hasattr(self.real_sock_conn,'settimeout'):
                self.real_sock_conn.settimeout(self.socket_timeout)
            if self.pyopenssl:
                self.sock_conn = self.SSL['m'].Connection(self.context, self.real_sock_conn)
            else:
                self.sock_conn = self.real_sock_conn
        else:
            self.sock_conn = self.socket.socket(self.socket.AF_INET, self.socket.SOCK_STREAM)
            if hasattr(self.sock_conn,'settimeout'):
                self.sock_conn.settimeout(self.socket_timeout)
            self.real_sock_conn = self.sock_conn

        self.hostname = host
        self.hostport = port

        try:
            self.sock_conn.connect((self.hostname, self.hostport))
            if self.ssl and not self.pyopenssl:
                if self.ssl_mod is not None:
                    self.sock_conn = self.ssl_mod.wrap_socket(self.real_sock_conn)
                else:
                    self.sock_conn = self.socket.ssl(self.real_sock_conn)
                # inform about certificate verification
                if not self.quiet:
                    mytxt = _("Warning: you are using an emergency SSL interface, SSL certificate can't be verified. Please install dev-python/pyopenssl")
                    self.Output.updateProgress(
                        "[%s:%s] %s" % (
                                brown(str(self.hostname)),
                                bold(str(self.hostport)),
                                blue(mytxt),
                        ),
                        importance = 1,
                        type = "warning",
                        header = self.output_header
                    )
                    mytxt = _("Service issuer")
                    self.Output.updateProgress(
                        "[%s:%s] %s: %s" % (
                                brown(str(self.hostname)),
                                bold(str(self.hostport)),
                                blue(mytxt),
                                self.sock_conn.issuer()
                        ),
                        importance = 1,
                        type = "warning",
                        header = self.output_header
                    )
        except self.socket.error, e:
            if e[0] == 111:
                mytxt = "%s: %s, %s: %s" % (_("Cannot connect to"),host,_("on port"),port,)
                raise ConnectionError("ConnectionError: %s" % (mytxt,))
            else:
                raise

        if not self.quiet:
            mytxt = _("Successfully connected to host")
            self.Output.updateProgress(
                "[%s:%s] %s" % (
                        brown(self.hostname),
                        bold(str(self.hostport)),
                        blue(mytxt),
                ),
                importance = 1,
                type = "info",
                header = self.output_header
            )

    def disconnect(self):
        if not self.real_sock_conn:
            return True
        if self.ssl and self.pyopenssl:
            self.sock_conn.shutdown()
            self.sock_conn.close()
        elif self.ssl and not self.pyopenssl:
            try:
                self.real_sock_conn.shutdown(self.socket.SHUT_RDWR)
            except self.socket.error:
                pass
        del self.sock_conn
        self.sock_conn = None
        try:
            self.real_sock_conn.close()
        except self.socket.error:
            pass
        if not self.quiet:
            mytxt = _("Successfully disconnected from host")
            self.Output.updateProgress(
                "[%s:%s] %s" % (
                        brown(self.hostname),
                        bold(str(self.hostport)),
                        blue(mytxt),
                ),
                importance = 1,
                type = "info",
                header = self.output_header
            )
        self.real_sock_conn = None
        # otherwise reconnect_socket won't work
        #self.hostname = None
        #self.hostport = None
