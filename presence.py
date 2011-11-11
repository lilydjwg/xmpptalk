import logging

import config

logger = logging.getLogger(__name__)

class PresenceMixin:
  def handle_userjoin_before(self, jid):
    # do block check here
    return True

  def handle_userjoin(self, jid):
    self.send_message(jid, config.welcome)
    logger.info('%s joined', jid)

  def handle_userleave(self, jid):
    for u in self.get_online_users():
      self.send_message(u, config.leave % self.get_name(jid))
    logger.info('%s left', jid)
