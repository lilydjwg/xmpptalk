import re
import io
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

# for i18n support
_ = lambda s: s
N_ = lambda a, b, n: a if n == 1 else b

# install to builtin namespace
builtins.__version__ = __version__
builtins._ = _
builtins.N_ = N_

PERM_USER = 1
PERM_GPADMIN = 2
PERM_SYSADMIN = 4

NOW = datetime.datetime.utcnow
DEFAULT_WELOME = _('Welcome to join this group!')

re_jid = re.compile(r'[^@ ]+@(?:[\w-]+\.)+\w{2,4}')
dateformat = _('%m-%d %H:%M:%S')
timeformat = _('%H:%M:%S')
logger = logging.getLogger(__name__)

AWAY    = _('离开')
XAWAY   = _('离开')
BUSY    = _('忙碌')
ONLINE  = _('在线')
CHAT    = _('和我说话吧')

xmpp_show_map = {
  '':     ONLINE,
  'away': AWAY,
  'dnd':  BUSY,
  'xa':   XAWAY,
  'chat': CHAT,
}

ONE_DAY = datetime.timedelta(hours=24)
CMD_QUIT = 1
CMD_RESTART = 2

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

escape_map = {}

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
      curses.setupterm()
      fg_color = str(curses.tigetstr("setaf") or
                 curses.tigetstr("setf") or "", "ascii")
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

def _setup_logging(hdl=None, color=False):
  log = logging.getLogger()
  if hdl is None:
    if not getattr(config, 'stderr_logging', True):
      return
    hdl = logging.StreamHandler()
    # if logging to stderr, determine color automatically
    curses.setupterm()
    color = getattr(config, 'color', False) or curses.tigetnum("colors") > 0

  formatter = TornadoLogFormatter(color=color)

  level = config.logging_level
  hdl.setLevel(level)
  hdl.setFormatter(formatter)
  log.setLevel(level)
  log.addHandler(hdl)
  logging.info('logging setup')

def setup_logging(hdl=None, color=False):
  _setup_logging()
  for log in config.additional_logging:
    _setup_logging(*log)

re_timeParser = re.compile(r'^(\d+)([smhd])?$')
TimeUnitMap = {
  '':  1,
  's': 1,
  'm': 60,
  'h': 3600,
  'd': 86400,
}
def parseTime(s):
  '''convert 3s，5d，1h，6m to seconds'''
  m = re_timeParser.match(s)
  if m is None:
    raise ValueError('not a time')
  n = int(m.group(1))
  u = m.group(2)
  if u is None:
    return n
  else:
    return n * TimeUnitMap[u]

