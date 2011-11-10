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

  def handle_message(self, sender, msg):
    q = self.message_queue
    if q and not q.empty():
      q.put((sender, msg))
      for i in range(min(MAX_MESSAGE_A_TIME, q.qsize())):
        self._handle_message(*q.get())
      if q.empty():
        self.message_queue = None
    else:
      self._handle_message(sender, msg)

  def _handle_message(self, sender, msg):
    # set self.current_user here
    raise NotImplementedError


  message_handler_register(pingpong)
  message_handler_register(command)
