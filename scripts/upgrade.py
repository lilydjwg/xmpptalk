#!/usr/bin/env python3
# vim:fileencoding=utf-8
#
# (C) Copyright 2012 lilydjwg <lilydjwg@gmail.com>
#
# This file is part of xmpptalk.
#
# xmpptalk is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# xmpptalk is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with xmpptalk.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
sys.path.insert(0, '.')
from models import connection, User, Log

col = connection[User.__database__][User.__collection__]
col.update({'last_seen': {'$exists': False}}, {'$set': {'last_seen': None}}, multi=True)
col.update({'last_speak': {'$exists': False}}, {'$set': {'last_speak': None}}, multi=True)
col.update({'prefix': {'$exists': True}}, {'$unset': {'prefix': 1}}, multi=True)

col = connection[Log.__database__][Log.__collection__]
col.update({'type': {'$exists': True}}, {'$unset': {'type': 1}}, multi=True)
