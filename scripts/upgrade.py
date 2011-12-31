#!/usr/bin/env python3
# vim:fileencoding=utf-8

import sys
sys.path.insert(0, '.')
from models import connection, User

col = connection[User.__database__][User.__collection__]
u = col.find_one()
q = {}
if 'last_seen' not in u:
  q['last_seen'] = None
if 'last_speak' not in u:
  q['last_speak'] = None
col.update({}, {'$set': q}, multi=True)
