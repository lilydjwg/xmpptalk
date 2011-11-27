from functools import wraps
import logging

from mongokit.schema_document import ValidationError

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

@command('pm', _('send private message to someone; need two arguments; spaces in nick should be escaped or quote the nick'))
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
  text.append(N_('%d users in total', '%d user in total', n) % n)
  self.reply('\n'.join(text))

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
