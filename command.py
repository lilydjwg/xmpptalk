#!/usr/bin/env python3
# vim: set fileencoding=utf-8:
# @Name: command.py
import shlex


class BaseHandler:
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

  def do_help(self):
    pass


class UserInfo:
  def do_history(self):
    """Chatting history"""
    pass

  def do_online(self):
    """The number of online people"""
    pass

  def do_Listing(self):
    """Listing all users in the group"""
    pass

  def do_admin(self):
    """Listing all administrators"""
    pass

  def do_seek(self, body):
    """Get one's information"""
    pass

  def do_stats(self):
    """Listing statistics"""
    pass


class UserSetting:
  def do_opendm(self, body):
    """Accepting direct message or not"""
    pass

  def do_prevent(self, body):
    """The resources you don't want to receive"""
    pass


class UserCommandMixin(BaseHandler, UserInfo, UserSetting):
  def do_nick(self, body):
    """Changing user's nick"""
    pass

  def do_dm(self, body):
    """Direct message"""
    pass

  def do_snooze(self, body):
    """Suspending the account"""
    pass

  def do_quit(self):
    """Quiting group"""
    pass


class ManagerCommandMixin(BaseHandler):
  pass


class SysCommandMixin(BaseHandler):
  pass
