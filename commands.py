#!/usr/bin/env python3
# vim:fileencoding=utf-8

from functools import wraps, partial

from misc import *

__commands = {}

def command(name, flags=PERM_USER):
  if name in __commands:
    raise ValueError('duplicate command %s' % name)
  def outerwrap(func):
    s = None
    @wraps(func)
    def innerwrap(self, arg):
      # TODO
      # if self.user['flags'] & flags:
      if True:
        nonlocal s
        s = self
        return func(self, arg)
      else:
        return False
    __commands[name] = partial(innerwrap, s)
    return innerwrap
  return outerwrap

class CommandMixin:
  @command('nick')
  def do_nick(self, new):
    print(new)

  def handle_command(self, msg):
    prefix = self.user['prefix']
    if not msg.startswith(prefix):
      return False

    cmds = msg[len(prefix):].split(None, 1)
    cmd = cmds[0]
    rest = len(cmds) == 2 and cmds[1] or '' 
    if cmd in __commands:
      if __commands[cmd](rest):
        # we handled it
        return True
    self.reply(_('No such command found.'))
    return True
