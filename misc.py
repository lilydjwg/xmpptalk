import re
import unicodedata
import hashlib
from functools import lru_cache

import config

'''constants and simple functions'''

# for i18n support
_ = lambda s: s

PERM_USER = 1
PERM_GPADMIN = 2
PERM_SYSADMIN = 4

re_jid = re.compile(r'[^@ ]+@(?:\w+\.)+\w{2,4}')

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
def hashjid(jid):
  '''
  return a representation of the jid with least conflict but still keep
  confidential
  '''
  m = hashlib.md5()
  bare = '%s/%s' % (jid.local, jid.domain)
  m.update(bare.encode())
  m.update(config.salt)
  domain = m.hexdigest()[:6]
  return '%s@%s' % (jid.local[:config.nick_maxwidth-7], domain)

__all__ = list(globals().keys())
