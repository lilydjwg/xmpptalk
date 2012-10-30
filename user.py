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
import logging
from functools import lru_cache
import datetime

import pymongo.errors

import models
import config
from welcome import Welcome
from misc import *

logger = logging.getLogger(__name__)

class UserMixin:
  # _cached_jid: the corresponding jid cached in _cached_user
  _cached_jid = _cached_user = None
  _cached_gp = None # Group or dict object
  current_jid = current_user = None

  @property
  def current_user(self):
    if self._cached_jid == self.current_jid:
      return self._cached_user

    if self.current_jid is None:
      return

    plainjid = str(self.current_jid.bare())
    user = models.connection.User.one({'jid': plainjid})

    # not in database
    if user is None:
      user = self.db_add_user(plainjid)
      Welcome(self.current_jid, self)

    self._cached_jid = self.current_jid
    self._cached_user = user
    return user

  def handle_userjoin_before(self):
    # TODO do block check here
    # may invoke twice
    return True

  def db_add_user(self, plainjid):
    '''
    add new user to database, return the added user; if alreadly exists, query
    and return it
    '''
    u = models.connection.User()
    u.jid = plainjid
    if plainjid == config.root:
      u.flag = PERM_USER | PERM_GPADMIN | PERM_SYSADMIN
    try:
      u.save()
    except pymongo.errors.DuplicateKeyError:
      return False
    return u

  def set_user_nick(self, *args, **kwargs):
    '''set sender's nick in database

    return the old `User` document, raise ValueError if duplicate
    use `increase` tells if this is an auto action so that the counter should
    not be increased

    This will reset the nick cache.
    '''
    try:
      return self._set_user_nick(*args, **kwargs)['nick']
    except TypeError: #None
      pass

  def set_self_nick(self, nick):
    '''set sender's nick in database

    return the old nick or None
    This will reset the nick cache.
    '''
    jid = str(self.current_jid.bare())
    user = self._set_user_nick(jid, nick)
    return user['nick']

  def _set_user_nick(self, plainjid, nick, increase=True):
    '''set a user's nick in database

    return the old `User` document, raise ValueError if duplicate
    `increase` tells if this is an auto action so that the counter should not
    be increased

    This will reset the nick cache.
    '''
    if getattr(config, "nick_change_interval", None):
      if self.current_user.nick_changes and \
         self.now - self.current_user.nick_lastchange < config.nick_change_interval:
        d = seconds2time(config.nick_change_interval.total_seconds())
        raise Forbidden(_("you can't change your nick too often; only once in %s is allowed.") % d)

    models.validate_nick(nick)
    if self.nick_exists(nick):
      raise ValueError(_('duplicate nick name: %s') % nick)

    self.user_get_nick.cache_clear()
    update = {
      '$set': {
        'nick': nick,
        'nick_lastchange': self.now,
      }
    }
    if increase:
      update['$inc'] = {'nick_changes': 1}

    ret = models.connection.User.collection.find_and_modify(
      {'jid': plainjid}, update
    )
    self.current_user.reload()
    return ret

  @lru_cache()
  def user_get_nick(self, plainjid):
    '''get a user's nick
    
    The result is cached so if any of the users's nicks change, call `cache_clear()`.
    Fallback to `self.get_name` if not found in database'''
    u = models.connection.User.one({'jid': plainjid}, ['nick'])
    nick = u.nick if u else None
    if nick is None:
      #fallback
      nick = self.get_name(plainjid)
    return nick

  def nick_exists(self, nick):
    return models.connection.User.find_one({'nick': nick}, {}) is not None

  def get_user_by_nick(self, nick):
    '''returns a `User` object
    
    nick should not be `None` or an arbitrary one will be returned'''
    return models.connection.User.find_one({'nick': nick})

  def get_user_by_jid(self, jid):
    return models.connection.User.one({'jid': jid})

  def user_reset_stop(self):
    models.connection.User.collection.update(
      {'jid': self.current_user.jid}, {'$set': {
        'stop_until': self.now,
      }}
    )
    #FIXME: if self.current_user has been deleted
    self.current_user.reload()
    self.user_update_presence(self.current_user)

  def user_reset_mute(self, user):
    models.connection.User.collection.update(
      {'jid': user.jid}, {'$set': {
        'mute_until': self.now,
      }}
    )
    self.user_update_presence(self.current_user)

  def user_update_msglog(self, msg):
    '''Note: This won't reload `self.current_user`'''
    models.connection.User.collection.update(
      {'jid': self.current_user.jid}, {'$inc': {
        'msg_chars': len(msg),
        'msg_count': 1,
      }}
    )

  def user_update_presence(self, user):
    if isinstance(user, str):
      user = self.get_user_by_jid(user)
      if not user:
        return

    prefix = ''

    sec1 = (user.mute_until - self.now).total_seconds()
    if sec1 > 0:
      t = (user.mute_until + config.timezoneoffset).strftime(dateformat)
      prefix += _('(muted until %s) ') % t

    sec2 = (user.stop_until - self.now).total_seconds()
    if sec2 > 0:
      t = (user.stop_until + config.timezoneoffset).strftime(dateformat)
      prefix += _('(stopped until %s) ') % t

    try:
      seconds = min(sec for sec in (sec1, sec2) if sec > 0)
    except ValueError:
      seconds = 0
    logger.debug('%s: %r seconds to go; sec1 = %r, sec2 = %r',
                 user.jid, seconds, sec1, sec2)
    self.xmpp_setstatus(
      prefix + self.group_status,
      to_jid=user.jid,
    )
    if seconds > 0.1:
      self.update_on_setstatus.add(user.jid)
      # XXX: Too many handlers?
      self.delayed_call(seconds, self.user_update_presence, user.jid)
    else:
      try:
        self.update_on_setstatus.remove(user.jid)
      except KeyError:
        pass

  def user_disappeared(self, plainjid):
    if plainjid == self.current_user.jid:
      self.current_user.last_seen == self.now

    models.connection.User.collection.update(
      {'jid': plainjid}, {'$set': {
        'last_seen': self.now,
      }}
    )
  def user_delete(self, user):
    logger.info('User %s (%s) left', user.nick, user.jid)
    user.delete()
    self.unsubscribe(user.jid)
    self.unsubscribe(user.jid, type='unsubscribed')

  def handle_userjoin(self, action=None):
    '''add the user to database and say Welcome'''
    # TODO: 根据 action 区别处理
    plainjid = str(self.current_jid.bare())

    self._cached_jid = None
    u = self.db_add_user(plainjid)
    if u is False:
      logger.warn('%s already in database', plainjid)
    else:
      Welcome(self.current_jid, self)
      logger.info('%s joined', plainjid)

  def handle_userleave(self, action=None):
    '''user has left, delete the user from database'''
    self.user_delete(self.current_user)
    self._cached_jid = None

  @property
  def group_status(self):
    gp = self._cached_gp or models.connection.Group.one()
    return gp.get('status', '')

  @group_status.setter
  def group_status(self, value):
    # external change takes effect here
    self._cached_gp = models.connection.Group.collection.find_and_modify(
      None, {'$set': {'status': value}}, new=True
    )
    for jid in self.update_on_setstatus.copy():
      self.user_update_presence(jid)

  @property
  def welcome(self):
    gp = self._cached_gp or models.connection.Group.one()
    return gp.get('welcome') or DEFAULT_WELOME

  @welcome.setter
  def welcome(self, value):
    # external change takes effect here
    self._cached_gp = models.connection.Group.collection.find_and_modify(
      None, {'$set': {'welcome': value}}, new=True
    )
