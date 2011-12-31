#!/usr/bin/env python3
# vim:fileencoding=utf-8

from models import connection, User

col = connection[User.__database__][User.__collection__]
col.update({}, {'$set': {'last_seen': None, 'last_speak': None}}, multi=True)
