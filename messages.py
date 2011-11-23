import logging
from functools import wraps

import commands
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

  def handle_message(self, msg):
    for h in _message_handles:
      if h(self, msg):
        break
    # self.dispatch_message(msg)

  def debug(self, msg):
    if msg == 'cli':
      from cli import repl
      repl(locals(), 'cmd.txt')
      return True
    elif msg == 'quit':
      raise SystemExit

  message_handler_register(debug)
  message_handler_register(pingpong)
  message_handler_register(command)
