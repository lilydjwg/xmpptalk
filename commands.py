#
# (C) Copyright 2012 lilydjwg <lilydjwg@gmail.com>
#
# This file is part of xmpptalk.
#
# xmpptalk is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# xmpptalk is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with xmpptalk.  If not, see <http://www.gnu.org/licenses/>.
#
from functools import wraps
from itertools import takewhile
import sys
import logging
import datetime
import struct
import subprocess

from mongokit.schema_document import ValidationError
from pyxmpp2.exceptions import JIDError

import models
from models import logmsg
from misc import *
import config

'''
command handling, should be called from messages.py
'''

# key is the command name, value is a (func, doc, flags) tuple
__commands = {}
logger = logging.getLogger(__name__)
__brief_help = ('nick', 'dm', 'old', 'online', 'stop', 'quit')

def command(name, doc, flags=PERM_USER):
  '''decorate and register a function that handles a command

  return False if should be considered not handled
  '''
  if name in __commands:
    raise ValueError('duplicate command %s' % name)
  def outerwrap(func):
    @wraps(func)
    def innerwrap(self, arg):
      if int(self.current_user.flag) & flags:
        return func(self, arg)
      else:
        return False
    innerwrap.__doc__ = doc
    __commands[name] = (innerwrap, doc, flags)
    return innerwrap
  return outerwrap

def handle_command(self, msg):
  # handle help message first; it is special since it need no prefix
  if msg == 'help':
    try:
      __commands[msg][0](self, '')
    except KeyError:
      self.reply(_('No help yet.'))
    return True

  prefix = config.prefix
  if not msg.startswith(prefix):
    return False

  msg = msg[len(prefix):]
  if len(tuple(takewhile(lambda x: not x.isidentifier() or x == '_', msg))) > 1:
    return False

  cmds = msg.split(None, 1)
  try:
    cmd = cmds[0]
  except IndexError:
    self.reply(_('No command specified.'))
    return True

  rest = len(cmds) == 2 and cmds[1] or ''
  if cmd in __commands:
    if __commands[cmd][0](self, rest) is not False:
      # we handled it
      return True
  self.reply(_('No such command found.'))
  return True
@command('about', _('about this software'))
def do_about(self, arg):
  secs = config.timezoneoffset.days * 86400 + config.timezoneoffset.seconds
  self.reply(_('xmpptalk is a groupchat bot using XMPP\n'
               'version: %s\n'
               'timezone: %+03d%02d\n'
               'https://github.com/lilydjwg/xmpptalk\n'
               'https://bitbucket.org/lilydjwg/xmpptalk'
              ) % (
                __version__,
                secs // 3600,
                (secs % 3600) // 60
              ))

@command('debug', _('suspend and open debug console'), PERM_SYSADMIN)
def do_debug(self, arg):
  if sys.stdin.isatty():
    import builtins
    from cli import repl
    from pyxmpp2.jid import JID
    old_ = builtins._
    g = locals()
    del g['repl'], g['builtins'], g['old_'], g['arg']
    repl(g, 'cmd.txt')
    builtins._ = old_
  else:
    self.reply(_('Error: stdin is not terminal.'))
  return True

@command('dm', _('send a direct message to someone; need two arguments; spaces in nick should be escaped or quote the nick; note that direct messages will alse be logged and can be reviewed by admins'))
def do_dm(self, arg):
  lex = Lex(arg)
  nick = lex.get_token()
  msg = lex.instream.read().lstrip()
  if nick and msg:
    u = self.get_user_by_nick(nick)
    if u:
      if not u.allow_pm or str(self.current_jid.bare()) in u.badpeople:
        self.reply(_('Sorry, %s does not accept direct messages from you.') % nick)
      else:
        self.send_message(u.jid, _('_DM_ [%s] ') % self.current_user.nick + msg)
    else:
      self.reply(_('Nobody with the nick "%s" found.') % nick)
  else:
    self.reply(_("arguments error: please give the user's nick and the message you want to send"))

@command('free', _('invode `free -m` and show its output'))
def do_free(self, arg):
  out = subprocess.getoutput('free -m')
  self.reply(out)
@command('help', _('display a brief help'))
def do_help(self, arg):
  help = []
  for name in __brief_help:
    __, doc, __ = __commands[name]
    help.append((name, doc))
  help.sort(key=lambda x: x[0])
  prefix = config.prefix
  text = [_('***brief command help***')]
  for name, doc in help:
    text.append('%s%s:\t%s' % (prefix, name, doc))
  text.append(_('For a detailed help, use "%slonghelp".') % prefix)
  self.reply('\n'.join(text))

@command('iam', _('show information about yourself'))
def do_iam(self, arg):
  self.reply(user_info(self.current_user, self.presence, show_lastseen=True))

@command('invite', _('invite someone to join'), PERM_GPADMIN)
def do_invite(self, arg):
  arg = arg.strip()
  jid, *args = arg.split()
  try:
    models.validate_jid(jid)
  except (ValidationError, JIDError) as e:
    self.reply(_('Error: %s') % str(e))
    return

  u = self.get_user_by_jid(jid)
  if u and not (args and args[0] == '-f'):
    self.reply(_('This user is already a member in this group, known as %s') % u.nick)
    return

  self.subscribe(jid)
  self.reply(_('Invitation sent, please wait for approval.'))

@command('kick', _('kick out someone'), PERM_GPADMIN)
def do_kick(self, arg):
  nick = arg.strip()
  u = self.get_user_by_nick(nick)
  if u:
    self.send_message(u.jid, _('Oops, you have been kicked!'))
    self.user_delete(u)
    self.reply(_('User %s (%s) has been kicked.') % (nick, u.jid))
    self.dispatch_message(
      _('User %s has been kicked.') % nick,
      but={self.current_user.jid, u.jid},
    )
  else:
    self.reply(_('Nobody with the nick "%s" found.') % nick)

@command('kickw', _('kick out someone with specified message'), PERM_GPADMIN)
def do_kickwith(self, arg):
  lex = Lex(arg)
  nick = lex.get_token()
  u = self.get_user_by_nick(nick)
  if u:
    msg = lex.instream.read().lstrip()
    self.send_message(u.jid, msg)
    self.user_delete(u)
    self.reply(_('User %s (%s) has been kicked.') % (nick, u.jid))
    self.dispatch_message(
      _('User %s has been kicked.') % nick,
      but={self.current_user.jid, u.jid},
    )
    self.ignore.add(u.jid)
  else:
    self.reply(_('Nobody with the nick "%s" found.') % nick)

@command('longhelp', _('display this detailed help'))
def do_longhelp(self, arg):
  help = []
  for name, (__, doc, flags) in __commands.items():
    if int(self.current_user.flag) & flags:
      help.append((name, doc))
  help.sort(key=lambda x: x[0])
  prefix = config.prefix
  text = [_('***detailed command help***')]
  for name, doc in help:
    text.append('%s%s:\t%s' % (prefix, name, doc))
  self.reply('\n'.join(text))

def get_nick_help():
  nick_help = _('change your nick; show your current nick if no new nick provided')
  if getattr(config, 'nick_change_interval', None):
    d = seconds2time(config.nick_change_interval.total_seconds())
    nick_help += _('. You can only change your nick once in %s') % d
  return nick_help

@command('nick', get_nick_help())
def do_nick(self, new):
  new_nick = new.strip()
  if not new_nick:
    old_nick = self.current_user.nick
    self.reply(_('Your current nick is: %s') % old_nick)
    return

  try:
    old_nick = self.set_self_nick(new_nick)
  except (ValueError, ValidationError, Forbidden) as e:
    self.reply(_('Error: %s') % e)
    return

  bare = self.current_jid.bare()
  self.update_roster(bare, new_nick)
  self.reply(_('Your nick name has changed to "%s"!') % new_nick)

  if old_nick is not None:
    msg = _('%s is now known as %s.') % (old_nick, new_nick)
    logmsg(self.current_jid, msg)
    for u in self.get_message_receivers():
      if u != bare:
        self.send_message(u, msg)

@command('old', _('show at most 50 history entries in an hour; if argument given, it specifies either the number of entries, or the time period passed from now (format is same as `stop\' command)'))
def do_old(self, arg):
  arg = arg.strip()
  if arg:
    for f in (oldNum, oldTime, oldOffline, oldSince):
      try:
        num, t = f(self, arg)
        if num == 0 and t is None:
          return
        break
      except ValueError:
        continue
    else:
      self.reply(_('can\'t understand your log lookup request'))
      return
  else:
    num = 50
    t = 60
  try:
    q = models.connection.Log.find(num, t)
  except (struct.error, OverflowError):
    self.reply(_('Overflow!'))
    return
  if q:
    if self.now - q[0].time > ONE_DAY:
      format = dateformat
    else:
      format = timeformat
  else:
    self.reply(_('No history entries match your criteria'))
    return

  text = []
  for l in q:
    try:
      m = '%s %s' % (
        (l.time + config.timezoneoffset).strftime(format),
        l.msg,
      )
    except AttributeError:
      logger.warn('malformed log messages: %r', l)
      continue
    text.append(m)
  self.reply('\n'.join(text))

@command('online', _('show online user list; if argument given, only nicks with the argument inbetween will be shown'))
def do_online(self, arg):
  header = _('online users list')
  if arg:
    header += _(' (with "%s" inbetween)') % arg
  text = []

  now = self.now
  for u in self.get_online_users():
    user = models.connection.User.one({'jid': str(u)})
    if user is None:
      continue
    if user.nick is None:
      user.nick = hashjid(user.jid)
      user.save()
    nick = user.nick
    if arg and nick.find(arg) == -1:
      continue

    line = '* ' + nick
    if user.mute_until > now:
      line += _(' <muted>')
    if user.stop_until > now:
      line += _(' <stopped>')

    st = self.get_xmpp_status(u)
    if st['show']:
      try:
        line += ' (%s)' % xmpp_show_map[st['show']]
      except KeyError:
        line += _(' (unknown)')
        logger.warn('unknown XMPP show: %s', st['show'])
    if st['status']:
      line += ' [%s]' % st['status'].strip()
    text.append(line)

  text.sort()
  n = len(text)
  text.insert(0, header)
  text.append(N_('%d user listed', '%d users listed', n) % n)
  self.reply('\n'.join(text))

@command('pm', _('deprecated, use the "dm" command instead.'))
def do_pm(self, arg):
  self.reply(_('This command is deprecated. Please use the "dm" command instead.'))

@command('quit', _('quit the group; only Gtalk users need this, other client users may just remove the buddy.'))
def do_quit(self, arg):
  self.reply(_('See you!'))
  self.user_delete(self.current_user)

@command('restart', _('restart the process'), PERM_SYSADMIN)
def do_restart(self, arg):
  self.xmpp_setstatus(_('Restarting...'))
  self.reply(_('Restarting...'))
  raise SystemExit(CMD_RESTART)

@command('say', _('send the following text literally'))
def do_say(self, arg):
  #FIXME: duplicate code of MessageMixin.handle_message
  msg = arg
  self.user_update_msglog(msg)
  msg = '[%s] ' % self.user_get_nick(str(self.current_jid.bare())) + msg
  if self.current_user.stop_until > self.now:
    self.user_reset_stop() # self.current_user is reloaded here
  self.dispatch_message(msg)

@command('setstatus', _("get or set the talkbot's status message; use 'None' to clear"), PERM_GPADMIN)
def do_setstatus(self, arg):
  st = self.group_status

  if not arg:
    self.reply(_('current group status: %s') % st)
    return

  if arg == 'None':
    arg = None
  self.xmpp_setstatus(arg)
  self.group_status = arg
  self.reply(_('ok.'))

@command('setwelcome', _("get or set the group's welcome message; use 'None' to clear"), PERM_GPADMIN)
def do_setwelcome(self, arg):
  wel = self.welcome

  if not arg:
    self.reply(_('current group welcome message: %s') % wel)
    return

  if arg == 'None':
    arg = None
  self.welcome = arg
  self.reply(_('ok.'))

@command('shutdown', _('shutdown the bot'), PERM_SYSADMIN)
def do_shutdown(self, arg):
  self.reply(_('Shutting down...'))
  self.dispatch_message(_('Shutting down by %s...') % \
                        self.user_get_nick(str(self.current_jid.bare())))
  raise SystemExit(CMD_QUIT)

@command('stop', _('stop receiving messages for some time; useful units: m, h, d. If you stop for 0 seconds, you wake up.'))
def do_stop(self, arg):
  arg = arg.strip()
  if not arg:
    self.reply(_('How long will you stop receiving messages?'))
    return

  try:
    n = parseTime(arg)
  except ValueError:
    self.reply(_("Sorry, I can't understand the time you specified."))
    return

  now = self.now
  if n == 0:
    if now < self.current_user.stop_until:
      self.user_reset_stop()
      self.reply(_('Ok, stop cancelled.'))
    else:
      self.reply(_('Not stopped yet.'))
    return

  try:
    dt = now + datetime.timedelta(seconds=n)
  except OverflowError:
    self.reply(_("Oops, it's too long."))
    return
  # PyMongo again...
  models.connection.User.collection.update(
    {'jid': self.current_user.jid}, {'$set': {
      'stop_until': dt,
    }}
  )
  self.current_user.reload()
  t = (dt + config.timezoneoffset).strftime(longdateformat)
  self.reply(_('Ok, stop receiving messages until %s. You can change this by another `stop` command.') % t)
  self.user_update_presence(self.current_user)

@command('mute', _('stop somebody from talking for the specified period of time; useful units: m, h, d'), PERM_GPADMIN)
def do_mute(self, arg):
  lex = Lex(arg)
  nick = lex.get_token()
  time = lex.instream.read().lstrip()

  if not time:
    self.reply(_('No time provided.'))
    return

  try:
    n = parseTime(time)
  except ValueError:
    self.reply(_("Sorry, I can't understand the time you specified."))
    return

  user = nick and self.get_user_by_nick(nick)
  if not user:
    self.reply(_('Nobody with the nick "%s" found.') % nick)
    return

  now = self.now
  if n == 0:
    if now < user.mute_until:
      self.user_reset_mute(user)
      self.send_message(user.jid, _('Muting has been cancelled.'))
      self.dispatch_message(
        _('Muting for %s has been cancelled.') % nick,
        but={self.current_user.jid, user.jid},
      )
      self.reply(_('Ok, mute for "%s" cancelled.') % nick)
    else:
      self.reply(_('"%s" not muted yet.') % nick)
    return

  try:
    dt = now + datetime.timedelta(seconds=n)
  except OverflowError:
    self.reply(_("Oops, it's too long."))
    return
  user.mute_until = dt
  # user.save() would complain about float instead of int
  models.connection.User.collection.update(
    {'jid': user.jid}, {'$set': {
      'mute_until': dt,
    }}
  )
  user.reload()
  t = (dt + config.timezoneoffset).strftime(dateformat)
  self.send_message(user.jid, _('You are disallowed to speak until %s') % t)
  args = dict(nick=nick, time=t)
  self.dispatch_message(
    _('%(nick)s is disallowed to speak until %(time)s.') % args,
    but={self.current_user.jid, user.jid},
  )
  self.reply(_('Ok, mute "%(nick)s" until %(time)s.') % args)
  self.user_update_presence(user)

@command('users', _('show all members; if argument given, only nicks with the argument inbetween will be shown'))
def do_users(self, arg):
  header = _('all users list')
  if arg:
    header += _(' (with "%s" inbetween)') % arg
  text = []

  q = models.connection.User.find(
    None, ['nick', 'msg_chars', 'msg_count'],
    sort=[('msg_count', 1), ('msg_chars', 1), ('nick', 1)])
  for u in q:
    if u.nick is None:
      u.nick = hashjid(u.jid)
      u.save()
    if arg and u.nick.find(arg) == -1:
      continue
    text.append('* %(nick)s (N=%(msg_count)d, C=%(msg_chars)d)' % u)

  n = len(text)
  text.insert(0, header)
  text.append(N_('%d user listed', '%d users listed', n) % n)
  self.reply('\n'.join(text))

@command('uptime', _('invode `uptime` and show its output'))
def do_uptime(self, arg):
  out = subprocess.getoutput('uptime')
  self.reply(out)

@command('whois', _('show information about others'))
def do_whois(self, arg):
  nick = arg.strip()
  u = self.get_user_by_nick(nick)
  if u:
    show_jid = int(self.current_user.flag) & PERM_GPADMIN
    self.reply(user_info(u, self.presence, show_jid))
  else:
    self.reply(_('Nobody with the nick "%s" found.') % nick)

def oldNum(self, arg):
  return int(arg), None

def oldTime(self, arg):
  return 10000, parseTime(arg) // 60 + 1

def oldSince(self, arg):
  if arg[0] != '+':
    raise ValueError
  return 10000, secondsSince(arg, self.now) // 60 + 1

def oldOffline(self, arg):
  if arg != '+':
    raise ValueError
  try:
    return 10000, (self.now - self.current_user.last_seen).total_seconds() // 60 + 1
  except TypeError:
    return 50, 60
