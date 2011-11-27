import re
import unicodedata

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

__all__ = list(globals().keys())
