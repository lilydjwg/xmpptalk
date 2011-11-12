#!/usr/bin/env python3
# vim: set fileencoding=utf-8:
# @Name: command.py
import shlex


class CommandMixinMixin:
  def unknown(self, message):
    pass

  def handle(self, message):
    lexer = shlex.shlex(message)
    command = lexer.get_token()
    body = lexer.instream.read().strip()
    try:
      meth = getattr(self, 'do_'+command, None)
      meth(body)
    except TypeError:
      self.unknown(command)


class UserCommandMixin(CommandMixinMixin):
  pass


class ManagerCommandMixin(CommandMixinMixin):
  pass


class SysCommandMixin(CommandMixinMixin):
  pass
