from functools import wraps

from mongokit.schema_document import ValidationError

from misc import *

'''
command handling, should be called from messages.py
'''

# key is the command name, value is a (func, doc) pair
__commands = {}

def command(name, doc, flags=PERM_USER):
  if name in __commands:
    raise ValueError('duplicate command %s' % name)
  def outerwrap(func):
    @wraps(func)
    def innerwrap(self, arg):
      if int(self.current_user.flag) & flags:
        return func(self, arg)
      else:
        return False
    __commands[name] = (innerwrap, doc)
    return innerwrap
  return outerwrap

@command('nick', _('change your nick; show your current nick if no new nick provided'))
def do_nick(self, new):
  new_nick = new.strip()
  if not new_nick:
    old_nick = self.current_user.nick
    self.reply(_('Your current nick is: %s') % old_nick)
    return True

  try:
    old_nick = self.set_self_nick(new_nick)
  except (ValueError, ValidationError) as e:
    self.reply(_('Error: %s') % e)
    return True

  bare = self.current_jid.bare()
  self.update_roster(bare, new_nick)
  self.reply(_('Your nick name has changed to "%s"!') % new_nick)

  if old_nick is not None:
    msg = _('%s 的昵称已更新为 %s。') % (old_nick, new_nick)
    for u in self.get_online_users():
      if u != bare:
        self.send_message(u, msg)

  return True

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
    if __commands[cmd][0](self, rest):
      # we handled it
      return True
  self.reply(_('No such command found.'))
  return True
