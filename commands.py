from functools import wraps

from misc import *

'''
command handling, should be called from messages.py
'''

__commands = {}

def command(name, flags=PERM_USER):
  if name in __commands:
    raise ValueError('duplicate command %s' % name)
  def outerwrap(func):
    @wraps(func)
    def innerwrap(self, arg):
      # TODO
      # if self.current_user.flag & flags:
      if True:
        return func(self, arg)
      else:
        return False
    __commands[name] = innerwrap
    return innerwrap
  return outerwrap

@command('nick')
def do_nick(self, new):
  # nick = stanza.body.split(None, 1)[1]
  # old_nick = self.get_name(sender)
  # self.update_roster(bare, nick)
  # self.send_message(sender, '昵称更新成功！')
  # msg = '%s 的昵称已更新为 %s。' % (old_nick, nick)
  # for u in self.get_online_users():
  #   if u.jid != bare:
  #     self.send_message(u.jid, msg)
  pass

def handle_command(self, msg):
  prefix = self.current_user.prefix
  if not msg.startswith(prefix):
    return False

  cmds = msg[len(prefix):].split(None, 1)
  cmd = cmds[0]
  rest = len(cmds) == 2 and cmds[1] or ''
  if cmd in __commands:
    if __commands[cmd](self, rest):
      # we handled it
      return True
  self.reply(_('No such command found.'))
  return True
