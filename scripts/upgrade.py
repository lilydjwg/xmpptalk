#!/usr/bin/env python3
# vim:fileencoding=utf-8

import sys
sys.path.insert(0, '.')
from models import connection, User

col = connection[User.__database__][User.__collection__]
col.update({'last_seen': {'$exists': False}}, {'$set': {'last_seen': None}}, multi=True)
col.update({'last_speak': {'$exists': False}}, {'$set': {'last_speak': None}}, multi=True)
