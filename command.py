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

  def do_help(self, body):
    pass


class UserInfo:
  def do_history(self, body):
    """Chatting history"""
    pass

  def do_online(self, body):
    """The number of online people"""
    pass

  def do_List(self, body):
    """List all users in the group"""
    pass

  def do_admin(self, body):
    """List all administrators"""
    pass

  def do_seek(self, body):
    """Get one's information"""
    pass

  def do_stats(self, body):
    """List statistics"""
    pass


class UserSetting:
  def do_opendm(self, body):
    """Accept direct message or not"""
    pass

  def do_prevent(self, body):
    """The resources you don't want to receive"""
    pass


class UserCommandMixin(BaseHandler, UserInfo, UserSetting):
  def do_nick(self, body):
    """Change user's nick"""
    pass

  def do_dm(self, body):
    """Direct message"""
    pass

  def do_snooze(self, body):
    """Suspending the account"""
    pass

  def do_quit(self, body):
    """Quiting group"""
    pass


class ManagerCommandMixin(BaseHandler):
  def do_invite(self, body):
    """Invite someone"""
    pass

  def do_block(self, body):
    """Forbid one's permission of chatting"""
    pass

  def do_kick(self, body):
    """Ban member"""
    pass

  def do_suadd(self, body):
    """Add/remove new administrator"""
    pass

  def do_desc(self, body):
    """Edit description of the group"""


class SuCommandMixin(ManagerCommandMixin):
  def do_top(self, body):
    """Display system tasks"""
    pass

  def do_restart(self, body):
    """Restart program"""
    pass
