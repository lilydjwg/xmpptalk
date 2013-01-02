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
import re
import os
import sys
import io
import fcntl
import time
import unicodedata
import hashlib
from functools import lru_cache
import builtins
import datetime
import logging
import curses

import config

'''constants and simple functions'''

__version__ = 'pre-alpha'

# install to builtin namespace
builtins.__version__ = __version__

# for i18n support
try:
  import gettext
  APP_NAME = "xmpptalk"
  LOCALE_DIR = os.path.abspath("locale")
  if not os.path.exists(LOCALE_DIR):
      LOCALE_DIR = "/usr/share/locale"
  gettext.bindtextdomain(APP_NAME, LOCALE_DIR)
  gettext.textdomain(APP_NAME)
  builtins._ = gettext.gettext
  builtins.N_ = gettext.ngettext
  import locale
  locale.setlocale(locale.LC_ALL, '')
except ImportError:
  builtins._ = lambda s: s
  builtins.N_ = lambda a, b, n: a if n == 1 else b

PERM_USER = 1
PERM_GPADMIN = 2
PERM_SYSADMIN = 4

DEFAULT_WELOME = _('Welcome to join this group!')

re_jid = re.compile(r'[^@ ]+@(?:[\w-]+\.)+\w{2,4}')
dateformat = _('%m-%d %H:%M:%S')
longdateformat = _('%Y-%m-%d %H:%M:%S')
timeformat = _('%H:%M:%S')
until_date = lambda dt, now: (dt + config.timezoneoffset).strftime(longdateformat) if dt > now else _('(N/A)')
logger = logging.getLogger(__name__)
lock_fd = [-1]

AWAY    = _('away')
XAWAY   = _('far away')
BUSY    = _('dnd')
ONLINE  = _('online')
CHAT    = _('chatty')
OFFLINE = _('offline')
UNAVAILABLE = _('unavailable')

xmpp_show_map = {
  '':     ONLINE,
  'away': AWAY,
  'dnd':  BUSY,
  'xa':   XAWAY,
  'chat': CHAT,
  'offline': OFFLINE,
  'unavailable': UNAVAILABLE,
}

ONE_DAY = datetime.timedelta(hours=24)
CMD_QUIT = 1
CMD_RESTART = 2

def show_privileges(flag):
  flag = int(flag)
  ret = []
  if flag & PERM_USER:
    ret.append(_('member'))
  if flag & PERM_GPADMIN:
    ret.append(_('group_admin'))
  if flag & PERM_SYSADMIN:
    ret.append(_('sys_admin'))
  return ', '.join(ret)

def user_info(user, presence, show_jid=True, show_lastseen=False):
  now = datetime.datetime.utcnow()
  ans= _(
    'Nick: %s\n'
    'Nick changed %d time(s), last at %s\n'
    '%d message(s), %d characters in total.\n'
    'Stopped Until: %s\n'
    'Muted Until: %s\n'
    'Joined At: %s\n'
    'Receive PM: %s\n'
    'Bad People: [%s]\n'
    'Privileges: %s'
  ) % (
    user['nick'],
    user['nick_changes'], (user['nick_lastchange'] + config.timezoneoffset).strftime(longdateformat),
    user['msg_count'], user['msg_chars'],
    until_date(user['stop_until'], now),
    until_date(user['mute_until'], now),
    (user['join_date'] + config.timezoneoffset).strftime(longdateformat),
    user['allow_pm'] and _('yes') or _('no'),
    ', '.join(user['badpeople']),
    show_privileges(user['flag']),
  )

  if user['jid'] in presence:
    ans += _('\nOnline Resources: [%s]') % ', '.join(presence[user['jid']].keys())
  else:
    show_lastseen = True

  if show_lastseen:
    if user['last_seen']:
      last_seen = (user['last_seen'] + config.timezoneoffset).strftime(longdateformat)
    else:
      last_seen = _('(Never)')
    ans += _('\nLast Online: %s') % last_seen

  if show_jid:
    ans = 'JID: %s\n' % user['jid'] + ans
  return ans

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
  if isinstance(jid, str):
    username, domain = jid.split('@')
  else:
    username, domain = jid.local, jid.domain
  bare = '%s/%s' % (username, domain)
  m.update(bare.encode())
  m.update(config.salt)
  domain = m.hexdigest()[:6]
  return '%s@%s' % (username[:config.nick_maxwidth-7], domain)

escape_map = {}

class Forbidden(Exception): pass
class Lex:
  def __init__(self, string):
    self.instream = io.StringIO(string)

  def get_token(self):
    ins = self.instream
    quote = None
    token = ''
    escaped = False
    while True:
      nextchar = ins.read(1)
      if not nextchar: # stream end
        return token
      elif escaped:
        token += escape_map.get(nextchar, nextchar)
        escaped = False
      elif nextchar == quote:
        return token
      elif nextchar in '\'"' and not quote:
        quote = nextchar
      elif nextchar == '\\':
        escaped = True
      elif nextchar.isspace():
        if quote:
          token += nextchar
        elif token:
          return token
      else:
        token += nextchar

def restart_if_failed(func, max_tries, args=(), kwargs={}, secs=60):
  '''
  re-run when some exception happens, until `max_tries` in `secs`
  '''
  import traceback
  from collections import deque

  dq = deque(maxlen=max_tries)
  while True:
    dq.append(time.time())
    try:
      func(*args, **kwargs)
    except:
      logger.error(traceback.format_exc())
      if len(dq) == max_tries and time.time() - dq[0] < secs:
        break
    else:
      break

class TornadoLogFormatter(logging.Formatter):
  def __init__(self, color, *args, **kwargs):
    super().__init__(self, *args, **kwargs)
    self._color = color
    if color:
      import curses
      curses.setupterm()
      if sys.hexversion < 50463728:
        fg_color = str(curses.tigetstr("setaf") or
                   curses.tigetstr("setf") or "", "ascii")
      else:
        fg_color = curses.tigetstr("setaf") or curses.tigetstr("setf") or b""
      self._colors = {
        logging.DEBUG: str(curses.tparm(fg_color, 4), # Blue
                     "ascii"),
        logging.INFO: str(curses.tparm(fg_color, 2), # Green
                    "ascii"),
        logging.WARNING: str(curses.tparm(fg_color, 3), # Yellow
                     "ascii"),
        logging.ERROR: str(curses.tparm(fg_color, 1), # Red
                     "ascii"),
      }
      self._normal = str(curses.tigetstr("sgr0"), "ascii")

  def format(self, record):
    try:
      record.message = record.getMessage()
    except Exception as e:
      record.message = "Bad message (%r): %r" % (e, record.__dict__)
    record.asctime = time.strftime(
      "%m-%d %H:%M:%S", self.converter(record.created))
    record.asctime += '.%03d' % ((record.created % 1) * 1000)
    prefix = '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]' % \
      record.__dict__
    if self._color:
      prefix = (self._colors.get(record.levelno, self._normal) +
            prefix + self._normal)
    formatted = prefix + " " + record.message
    if record.exc_info:
      if not record.exc_text:
        record.exc_text = self.formatException(record.exc_info)
    if record.exc_text:
      formatted = formatted.rstrip() + "\n" + record.exc_text
    return formatted.replace("\n", "\n    ")

def _setup_logging(hdl=None, level=config.logging_level, color=False):
  log = logging.getLogger()
  if hdl is None:
    if not getattr(config, 'stderr_logging', True) or '--fork' in sys.argv:
      pid = os.fork()
      if pid > 0:
        try:
          print('forked as pid %d' % pid)
        finally:
          os._exit(0)
      return
    hdl = logging.StreamHandler()
    # if logging to stderr, determine color automatically
    curses.setupterm()
    color = getattr(config, 'color', False) or curses.tigetnum("colors") > 0

  formatter = TornadoLogFormatter(color=color)

  hdl.setLevel(level)
  hdl.setFormatter(formatter)
  log.setLevel(logging.DEBUG)
  log.addHandler(hdl)
  logging.info('logging setup')

def setup_logging(hdl=None, level=config.logging_level, color=False):
  f = '/tmp/talkbot.%s' % config.jid.split('/', 1)[0]
  fd = lock_fd[0] = os.open(f, os.O_CREAT | os.O_WRONLY, 0o600)
  try:
    # FIXME: This works well on Linux and FreeBSD, but may not work well on
    # AIX and OpenBSD
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
  except:
    print('Error locking', f, file=sys.stderr)
    sys.exit(1)
  _setup_logging()
  for log in config.additional_logging:
    _setup_logging(*log)

re_timeParser = re.compile(r'(\d+)([smhd]?)')
TimeUnitMap = {
  '':  1,
  's': 1,
  'm': 60,
  'h': 3600,
  'd': 86400,
}
def parseTime(s):
  '''convert 3s，5d，1h30m，6m to seconds'''
  pos = 0
  t = 0
  while pos < len(s):
    m = re_timeParser.match(s, pos)
    if m is None:
      raise ValueError('bad time period: %s' % s)
    t += int(m.group(1)) * TimeUnitMap[m.group(2)]
    pos = m.end()
  return t

def seconds2time(s):
  ans = []
  d, s = divmod(s, 86400)
  if d:
    ans.append(N_('%d day', '%d days', d) % d)
  h, s = divmod(s, 3600)
  if h:
    ans.append(N_('%d hour', '%d hours', h) % h)
  m, s = divmod(s, 60)
  if m:
    ans.append(N_('%d minute', '%d minutes', m) % m)
  if s:
    ans.append(N_('%d second', '%d seconds', s) % s)
  return _('  ')[:-1].join(ans)

re_timeSince = re.compile(r'\+(\d+-\d+ )?(\d+:\d+)')
def secondsSince(s, now):
  m = re_timeSince.match(s)
  localnow = now + config.timezoneoffset
  if m is None:
    raise ValueError
  if m.group(1) is None:
    d = localnow.strftime('%Y-%m-%d ')
  else:
    d = localnow.strftime('%Y-') + m.group(1)
  dt = datetime.datetime.strptime(d + m.group(2), '%Y-%m-%d %H:%M') - config.timezoneoffset
  ret = (now-dt).total_seconds()
  if dt > now:
    if m.group(1) is None:
      ret += 86400 # yesterday
    else:
      # last year
      dt = datetime.datetime(dt.year-1, dt.month, dt.day, dt.hour, dt.minute, dt.second)
      ret = (now-dt).total_seconds()
  return ret
