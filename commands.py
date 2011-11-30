from functools import wraps
import logging
import datetime

from mongokit.schema_document import ValidationError

import logdb
from models import connection
from misc import *

'''
command handling, should be called from messages.py
'''

# key is the command name, value is a (func, doc, flags) tuple
__commands = {}
logger = logging.getLogger(__name__)

def command(name, doc, flags=PERM_USER):
  '''decorate and register a function that handles a command

  return False if should be considered not handled
  '''
  if name in __commands:
    raise ValueError('duplicate command %s' % name)
  def outerwrap(func):
    @wraps(func)
    def innerwrap(self, arg):
      if int(self.current_user.flag) & flags:
        return func(self, arg)
      else:
        return False
    innerwrap.__doc__ = doc
    __commands[name] = (innerwrap, doc, flags)
    return innerwrap
  return outerwrap

@command('nick', _('change your nick; show your current nick if no new nick provided'))
def do_nick(self, new):
  new_nick = new.strip()
  if not new_nick:
    old_nick = self.current_user.nick
    self.reply(_('Your current nick is: %s') % old_nick)
    return

  try:
    old_nick = self.set_self_nick(new_nick)
  except (ValueError, ValidationError) as e:
    self.reply(_('Error: %s') % e)
    return

  bare = self.current_jid.bare()
  self.update_roster(bare, new_nick)
  self.reply(_('Your nick name has changed to "%s"!') % new_nick)

  if old_nick is not None:
    msg = _('%s 的昵称已更新为 %s。') % (old_nick, new_nick)
    logdb.lognick(self.current_jid, msg)
    for u in self.get_online_users():
      if u != bare:
        self.send_message(u, msg)

@command('help', _('display this help'))
def do_help(self, arg):
  help = []
  for name, (__, doc, flags) in __commands.items():
    if int(self.current_user.flag) & flags:
      help.append((name, doc))
  help.sort(key=lambda x: x[0])
  prefix = self.current_user.prefix
  text = [_('***command help***')]
  for name, doc in help:
    text.append('%s%s:\t%s' % (prefix, name, doc))
  self.reply('\n'.join(text))

@command('pm', _('send a private message to someone; need two arguments; spaces in nick should be escaped or quote the nick'))
def do_pm(self, arg):
  lex = Lex(arg)
  nick = lex.get_token()
  msg = lex.instream.read().lstrip()
  if nick and msg:
    u = self.get_user_by_nick(nick)
    if u:
      if not u.allow_pm or str(self.current_jid.bare()) in u.badpeople:
        self.reply(_('Sorry, %s does not accept private messages from you.') % nick)
      else:
        self.send_message(u.jid, _('_PM_ [%s] ') % self.current_user.nick + msg)
    else:
      self.reply(_('Nobody with the nick "%s" found.') % nick)
  else:
    self.reply(_("arguments error: please give the user's nick and the message you want to send"))

@command('online', _('show online user list; if argument given, only nicks with the argument will be shown'))
def do_online(self, arg):
  header = _('online users list')
  if arg:
    header += _(' (with "%s" inbetween)') % arg
  text = []

  for u in self.get_online_users():
    nick = self.user_get_nick(str(u))
    if arg and nick.find(arg) == -1:
      continue

    st = self.get_xmpp_status(u)
    line = '* ' + nick
    if st['show']:
      line += ' (%s)' % xmpp_show_map[st['show']]
    if st['status']:
      line += ' [%s]' % st['status']
    text.append(line)

  text.sort()
  n = len(text)
  text.insert(0, header)
  text.append(N_('%d user in listed', '%d users listed', n) % n)
  self.reply('\n'.join(text))

@command('old', _('show history in an hour; if argument given, it specifies the numbers of history entries to show'))
def do_old(self, arg):
  arg = arg.strip()
  if arg:
    try:
      num = int(arg)
      t = None
    except ValueError:
      self.reply(_('argument should be an integer'))
      return
  else:
    num = 50
    t = 60
  q = connection.Log.find(num, t)
  if q:
    if datetime.datetime.utcnow() - q[0].time > ONE_DAY:
      format = '%m-%d %H:%M:%S'
    else:
      format = '%H:%M:%S'
  else:
    self.reply(_('没有符合的聊天记录。'))
    return

  text = []
  for l in q:
    try:
      m = '%s %s' % (
        (l.time + config.timezoneoffset).strftime(format),
        l.msg,
      )
    except AttributeError:
      logger.warn('malformed log messages: %r', l)
      continue
    text.append(m)
  self.reply('\n'.join(text))

@command('setstatus', _("get or set the talkbot's status message; use 'None' to clear"), PERM_GPADMIN)
def do_setstatus(self, arg):
  gp = connection.Group.one()
  if gp is None:
    gp = connection.Group()

  if not arg:
    self.reply(_('current group status: %s') % gp.status)
    return

  if arg == 'None':
    arg = None
  self.xmpp_setstatus(arg)
  gp.status = arg
  gp.save()
  self.reply(_('ok.'))

@command('restart', _('restart the process'), PERM_SYSADMIN)
def do_restart(self, arg):
  self.reply(_('Restarting...'))
  self.dispatch_message(_('Restarting by %s...') % \
                        self.user_get_nick(str(self.current_jid.bare())))
  raise SystemExit(CMD_RESTART)

@command('quit', _('quit the bot'), PERM_SYSADMIN)
def do_quit(self, arg):
  self.reply(_('Quitting...'))
  self.dispatch_message(_('Quitting by %s...') % \
                        self.user_get_nick(str(self.current_jid.bare())))
  raise SystemExit(CMD_QUIT)

def handle_command(self, msg):
  # handle help message first; it is special since it need no prefix
  if msg == 'help':
    try:
      __commands[msg][0](self, '')
    except KeyError:
      self.reply(_('No help yet.'))
    return True

  prefix = self.current_user.prefix
  if not msg.startswith(prefix):
    return False

  cmds = msg[len(prefix):].split(None, 1)
  try:
    cmd = cmds[0]
  except IndexError:
    self.reply(_('No command specified.'))
    return True

  rest = len(cmds) == 2 and cmds[1] or ''
  if cmd in __commands:
    if __commands[cmd][0](self, rest) is not False:
      # we handled it
      return True
  self.reply(_('No such command found.'))
  return True
