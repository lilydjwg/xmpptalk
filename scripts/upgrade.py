#!/usr/bin/env python3
# vim:fileencoding=utf-8

import sys
sys.path.insert(0, '.')
from models import connection, User, Log

col = connection[User.__database__][User.__collection__]
col.update({'last_seen': {'$exists': False}}, {'$set': {'last_seen': None}}, multi=True)
col.update({'last_speak': {'$exists': False}}, {'$set': {'last_speak': None}}, multi=True)
col.update({'prefix': {'$exists': True}}, {'$unset': {'prefix': 1}}, multi=True)

col = connection[Log.__database__][Log.__collection__]
col.update({'type': {'$exists': True}}, {'$unset': {'type': 1}}, multi=True)
