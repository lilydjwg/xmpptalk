import logging

from models import connection, User

logger = logging.getLogger(__name__)

class UserMixin:
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
    self._cached_jid = self.current_jid
    self._cached_user = user
    return user

  def add_user(self, pjid):
    self._cached_jid = None
    u = connection.User()
    u.jid = pjid
    u.save()
    logger.info('User added: %r', u)

