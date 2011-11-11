import logging

import config

logger = logging.getLogger(__name__)

class PresenceMixin:
  def handle_userjoin_before(self, jid):
    # do block check here
    # may invoke twice
    return True

  def handle_userjoin(self, jid, action):
    # TODO: 邀请好友成功的区别处理
    self.add_user(str(jid.bare()))
    self.send_message(jid, config.welcome)
    logger.info('%s joined', jid)

  def handle_userleave(self, jid, action):
    # TODO: 删除好友成功的区别处理
    # for u in self.get_online_users():
    #   self.send_message(u, config.leave % self.get_name(jid))
    #TODO: 从数据库删除
    logger.info('%s left', jid)
