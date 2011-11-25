import logging
from functools import wraps

import commands
import config
from misc import *

logger = logging.getLogger(__name__)
_message_handles = []

def message_handler_register(func):
  # use a register func instead of decorator so that it's easier to (re-)order
  # the handlers
  _message_handles.append(func)

class MessageMixin:
  message_queue = None

  def pingpong(self, msg):
    if msg == 'ping':
      self.reply('pong')
      return True
    return False

  def command(self, msg):
    return commands.handle_command(self, msg)

  def filter_otr(self, msg):
    if msg.startswith('?OTR'):
      self.reply(_('你的客户端正在尝试使用 OTR 加密，但本群并不支持。'))
      return True
    else:
      return False

  def filter_autoreply(self, msg):
    if msg in config.filtered_message:
      self.reply(_('请不要设置自动回复。'))
      return True
    else:
      return False

  def give_help(self, msg):
    '''special handling for help messages'''
    if config.help_regex.match(msg):
      return commands.handle_command(self, 'help')
    else:
      return False

  def handle_message(self, msg):
    for h in _message_handles:
      if h(self, msg):
        break
    else:
      self.dispatch_message(msg)

  def dispatch_message(self, msg):
    #TODO logging
    curbare = self.current_jid.bare()
    for u in self.get_online_users():
      if u != curbare:
        s = '[%s] ' % self.get_name(self.current_jid)
        self.send_message(u, s+msg)
    return True

  def debug(self, msg):
    if msg == 'cli':
      from cli import repl
      repl(locals(), 'cmd.txt')
      return True
    elif msg == 'quit':
      raise SystemExit

  message_handler_register(debug)
  message_handler_register(pingpong)
  message_handler_register(give_help)
  message_handler_register(command)
  message_handler_register(filter_autoreply)
  message_handler_register(filter_otr)
