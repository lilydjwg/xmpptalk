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
import hashlib
import unicodedata
from functools import lru_cache

re_jid = re.compile(r'[^@ ]+@(?:[\w-]+\.)+\w{2,4}')

def validate_jid(jid):
  if not re_jid.match(jid):
    raise ValueError(_('wrong jid format: %s') % jid)
  return True

def validate_nick(nick, max_width, allowed_symbols):
  '''``nick`` should be already stripped if you only allow spaces in between'''
  if not nick:
    raise ValueError(_('no nickname provided'))
  l = width(nick)
  if l > max_width:
    raise ValueError(
      _('nickname too long (%d-character width), max is %d') % (l, max_width))

  for i in nick:
    cat = unicodedata.category(i)
    # Lt & Lm are special chars
    if (not (cat.startswith('L') or cat.startswith('N')) \
        or cat in ('Lm', 'Lt')) and i not in allowed_symbols:
      raise ValueError(
        _("nickname `%s' contains disallowed character: '%c'") % (nick, i))
  return True

def width(s, ambiwidth=2):
  if ambiwidth == 2:
    double = ('W', 'A')
  elif ambiwidth == 1:
    double = ('W',)
  else:
    raise ValueError('ambiwidth should be either 1 or 2')

  count = 0
  for i in s:
    if unicodedata.east_asian_width(i) in double:
      count += 2
      continue
    count += 1
  return count

@lru_cache()
def hashjid(jid, salt, max_width):
  '''
  return a representation of the jid with least conflict but still keep
  confidential
  '''
  m = hashlib.md5()
  username, host = jid.split('@')
  bare = '%s/%s' % (username, host)
  m.update(bare.encode())
  m.update(salt)
  host = m.hexdigest()[:6]
  return '%s@%s' % (username[:max_width-7], host)
