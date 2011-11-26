import logging
from functools import lru_cache

import pymongo.errors

from models import connection
import config
from greenlets import Welcome

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

    # not registered
    user = self.db_add_user(plainjid)

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

  def set_user_nick(self, plainjid, nick):
    '''
    return the old nick or None
    This will reset the nick cache.
    '''
    self.user_get_nick.cache_clear()
    # XXX: mongokit currently does not support find_and_modify
    return connection.User.collection.find_and_modify(
      {'jid': plainjid},
      {'$set': {'name': nick}}
    ).nick

  @lru_cache()
  def user_get_nick(self, plainjid):
    u = connection.User.one({'jid': plainjid})
    return u.name

  def handle_userjoin(self, action):
    # TODO: 邀请好友成功的区别处理
    plainjid = str(self.current_jid.bare())

    self._cached_jid = None
    u = self.db_add_user(plainjid)

    wel = Welcome(self.current_jid, self)
    logger.info('%s joined', plainjid)

  def handle_userleave(self, action):
    # TODO: 删除好友成功的区别处理
    # for u in self.get_online_users():
    #   self.send_message(u, config.leave % self.get_name(plainjid))
    #TODO: 从数据库删除
    ret = self.current_user.delete()
    self._cached_jid = None

    logger.info('%s left', self.current_jid)
