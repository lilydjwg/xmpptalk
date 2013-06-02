#
# (C) Copyright 2012-2013 lilydjwg <lilydjwg@gmail.com>
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
import re
import datetime

from .dbconn import get_db

_colname = 'log'

def logmsg(jid, msg, now=None):
  '''
  save a message log to database

  jid: a string representation of the user's full jid
  msg: the message itself
  now: current UTC time if you've got it

  A simple proof for the value of ``now``:

  In [3]: %timeit datetime.datetime.utcnow()
  1000000 loops, best of 3: 1.29 us per loop

  In [4]: %timeit if None is None: a = None
  10000000 loops, best of 3: 62 ns per loop
  '''
  if now is None:
    now = datetime.datetime.utcnow()
  log = {
    'time': now,
    'jid': jid,
    'msg': msg,
  }
  get_db()[_colname]save(log)

def find(n, after=None, bare_jid=None):
  '''
  find ``n`` recent messages after time ``after``.
  '''
  query = {}
  if after is not None:
    query['time'] = {'$gt': after}
  if bare_jid is not None:
    query['jid'] = {'$regex': '^' + re.escape(bare_jid) + '(/|$)'}

  col = get_db()[_colname]
  l = list(col.find(query).sort('$natural', -1).limit(n))
  l.reverse()
  return l
