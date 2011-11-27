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
    u = connection.User()
    u.jid = plainjid
    try:
      u.save()
    except pymongo.errors.DuplicateKeyError:
      u = connection.User.one({'jid': plainjid})
    return u

  def set_user_nick(self, *args, **kwargs):
    '''
    return the old nick or None
    This will reset the nick cache.
    '''
    return self._set_user_nick(*args, **kwargs)['nick']

  def set_self_nick(self, nick):
    '''
    return the old nick or None
    This will reset the nick cache.
    '''
    jid = str(self.current_jid.bare())
    user = self._set_user_nick(jid, nick)
    return user['nick']

  def _set_user_nick(self, plainjid, nick, increase=True):
    '''
    return the old `User` document, raise ValueError if duplicate
    This will reset the nick cache.
    '''
    models.validate_nick(nick)
    if self.nick_exists(nick):
      raise ValueError(_('duplicate nick name'))

    self.user_get_nick.cache_clear()
    update = {
      '$set': {
        'nick': nick,
        'nick_lastchange': datetime.datetime.utcnow(),
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
    u = connection.User.one({'jid': plainjid})
    return u.nick

  def nick_exists(self, nick):
    return connection.User.find_one({'nick': nick}, {}) is not None

  def handle_userjoin(self, action):
    # TODO: 根据 action 区别处理
    plainjid = str(self.current_jid.bare())

    self._cached_jid = None
    u = self.db_add_user(plainjid)

    Welcome(self.current_jid, self)
    logger.info('%s joined', plainjid)

  def handle_userleave(self, action):
    # TODO: 根据 action 区别处理
    # for u in self.get_online_users():
    #   self.send_message(u, config.leave % self.get_name(plainjid))
    ret = self.current_user.delete()
    self._cached_jid = None

    logger.info('%s left', self.current_jid)
