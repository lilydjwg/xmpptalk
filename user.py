import logging
from functools import lru_cache
import datetime

import pymongo.errors

import models
from models import connection
import config
from greenlets import Welcome
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
    user = connection.User.one({'jid': plainjid})

    # not in database
    if user is None:
      user = self.db_add_user(plainjid)
      Welcome(self.current_jid, self, use_roster_nick=True)

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
    u = connection.User()
    u.jid = plainjid
    if plainjid == config.root:
      u.flag = PERM_USER | PERM_GPADMIN | PERM_SYSADMIN
    try:
      u.save()
    except pymongo.errors.DuplicateKeyError:
      u = connection.User.one({'jid': plainjid})
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
    models.validate_nick(nick)
    if self.nick_exists(nick):
      raise ValueError(_('duplicate nick name: %s') % nick)

    self.user_get_nick.cache_clear()
    update = {
      '$set': {
        'nick': nick,
        'nick_lastchange': NOW(),
      }
    }
    if increase:
      update['$inc'] = {'nick_changes': 1}

    # XXX: mongokit currently does not support find_and_modify
    return connection.User.collection.find_and_modify(
      {'jid': plainjid}, update
    )

  @lru_cache()
  def user_get_nick(self, plainjid):
    '''get a user's nick
    
    The result is cached so if any of the users's nicks change, call `cache_clear()`.
    Fallback to `self.get_name` if not found in database'''
    u = connection.User.one({'jid': plainjid}, ['nick'])
    nick = u.nick if u else None
    if nick is None:
      #fallback
      nick = self.get_name(plainjid)
    return nick

  def nick_exists(self, nick):
    return connection.User.find_one({'nick': nick}, {}) is not None

  def get_user_by_nick(self, nick):
    '''returns a `User` object
    
    nick should not be `None` or an arbitrary one will be returned'''
    return connection.User.find_one({'nick': nick})

  def get_user_by_jid(self, jid):
    return connection.User.one({'jid': jid})

  def user_reset_stop(self):
    connection.User.collection.update(
      {'jid': self.current_user.jid}, {'$set': {
        'stop_until': NOW(),
      }}
    )
    self.current_user.reload()
    self.xmpp_setstatus(self.group_status, to_jid=self.current_jid)

  def user_update_presence(self, user):
    if isinstance(user, str):
      user = self.get_user_by_jid(user)
      if not user:
        return

    now = NOW()
    prefix = ''

    sec1 = (user.mute_until - now).total_seconds()
    if sec1 > 0:
      t = (user.mute_until + config.timezoneoffset).strftime(dateformat)
      prefix += _('(muted until %s) ') % t

    sec2 = (user.stop_until - now).total_seconds()
    if sec2 > 0:
      t = (user.stop_until + config.timezoneoffset).strftime(dateformat)
      prefix += _('(stopped until %s) ') % t

    if sec1 > sec2 and sec1 > 0:
      seconds = sec1
    elif sec1 < sec2 and sec2 > 0:
      seconds = sec2
    else:
      seconds = 0

    logger.debug('%s: %d seconds to go; sec1 = %d, sec2 = %d',
                 user.jid, seconds, sec1, sec2)
    self.xmpp_setstatus(
      prefix + self.group_status,
      to_jid=user.jid,
    )
    if seconds:
      self.update_on_setstatus.add(user.jid)
      # XXX: Too many handlers?
      self.delayed_call(seconds, self.user_update_presence, user.jid)
    else:
      try:
        self.update_on_setstatus.remove(user.jid)
      except KeyError:
        pass

  def handle_userjoin(self, action=None):
    '''add the user to database and say Welcome'''
    # TODO: 根据 action 区别处理
    plainjid = str(self.current_jid.bare())

    self._cached_jid = None
    u = self.db_add_user(plainjid)

    Welcome(self.current_jid, self)
    logger.info('%s joined', plainjid)

  def handle_userleave(self, action=None):
    '''user has left, delete the user from database'''
    # TODO: 根据 action 区别处理
    self.current_user.delete()
    self._cached_jid = None

    logger.info('%s left', self.current_jid)

  @property
  def group_status(self):
    gp = self._cached_gp or connection.Group.one()
    if gp is None:
      return None
    else:
      return gp.get('status', None)

  @group_status.setter
  def group_status(self, value):
    # external change takes effect here
    self._cached_gp = connection.User.collection.find_and_modify(
      None, {'$set': {'status': value}}, new=True
    )
    for jid in self.update_on_setstatus:
      self.user_update_presence(jid)
  @property
  def welcome(self):
    gp = self._cached_gp or connection.Group.one()
    if gp is None:
      return None
    else:
      return gp.get('welcome', None)

  @welcome.setter
  def welcome(self, value):
    # external change takes effect here
    self._cached_gp = connection.User.collection.find_and_modify(
      None, {'$set': {'welcome': value}}, new=True
    )
