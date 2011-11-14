import logging
from functools import wraps

import commands
from misc import *

logger = logging.getLogger(__name__)
__message_handles = []

def message_handler_register(func):
  # use a register func instead of decorator so that it's easier to (re-)order
  # the handlers
  __message_handles.append(func)

class MessageMixin:
  message_queue = None

  def pingpong(self, msg):
    if msg == 'ping':
      self.reply('pong')
      return True
    return False

  def command(self, msg):
    return commands.handle_command(self, msg)

  def handle_message(self, sender, msg):
    logger.warn(self.current_user)
    if msg == 'cli':
      from cli import repl
      repl(locals(), 'cmd.txt')

  message_handler_register(pingpong)
  message_handler_register(command)
