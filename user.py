import logging

import pymongo.errors

from models import connection, User
import config

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
    # do block check here
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

  def handle_userjoin(self, action):
    # TODO: 邀请好友成功的区别处理
    plainjid = str(self.current_jid.bare())

    self._cached_jid = None
    u = self.db_add_user(plainjid)

    self.send_message(self.current_jid, config.welcome)
    logger.info('%s joined', plainjid)

  def handle_userleave(self, action):
    # TODO: 删除好友成功的区别处理
    # for u in self.get_online_users():
    #   self.send_message(u, config.leave % self.get_name(plainjid))
    #TODO: 从数据库删除
    ret = self.current_user.delete()
    logger.warn('User.delete returns: %r', ret)
    self._cached_jid = None

    logger.info('%s left', self.current_jid)
