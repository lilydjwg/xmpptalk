#!/usr/bin/env python3
# vim:fileencoding=utf-8

from functools import wraps

from misc import *

__message_handles = []

def message_handler_register(func):
  # use a register func instead of decorator so that it's easier to (re-)order
  # the handlers
  __message_handles.append(func)

class MessageMixin:
  def pingpong(self, msg):
    if msg == 'ping':
      self.reply('pong')
      return True
    return False

  def command(self, msg):
    return self.handle_command(msg)

  message_handler_register(pingpong)
  message_handler_register(command)
