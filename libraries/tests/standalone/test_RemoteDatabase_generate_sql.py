# -*- coding: utf-8 -*-
import sys
from entropy.const import const_convert_to_unicode
from entropy.services.skel import RemoteDatabase
rd = RemoteDatabase()
action = "insert"
table = const_convert_to_unicode("òtableò", "utf-8")
data = {
    'user': const_convert_to_unicode("Aleò", 'utf-8'),
    'name': const_convert_to_unicode("Pippo", 'utf-8'),
}
sql = rd._generate_sql(action, table, data)
sys.stdout.write(sql.encode("utf-8") + "\n")
