import logging

from greenlet import greenlet

import config
from misc import *

logger = logging.getLogger(__name__)

class Welcome(greenlet):
  def __init__(self, jid, xmpp):
    '''jid is a full `JID`, xmpp is the bot itself'''
    super().__init__()
    self.switch(jid, xmpp)

  def run(self, jid, s):
    s.send_message(jid, config.welcome)
    s.get_vcard(jid, self.switch)
    stanza = self.parent.switch()
    if stanza.stanza_type == 'error':
      nick = s.get_name(jid)
      msg = _('Please choose a nick name by answering "%snick your_nick", '\
              'or it will be "%s".') % (
        config.user_default_prefix, nick
      )
    else:
      nick = stanza.get_all_payload()[0].element.find('{vcard-temp}FN').text
      while self.nick_exists(nick):
        nick += '_'
      msg = _('Would you like to use "%s" as your nick, '\
              'or use "%snick your_nick" to choose another') % (
        nick, config.user_default_prefix
      )
    s.send_message(jid, msg)
    s.set_user_nick(str(jid.bare()), nick, increase=False)
    logger.info('%s joined with nick %s', jid, nick)
    # TODO: hook to `user_get_nick`
    #       if the user's initial nick has been gotten, set `nick_changes` to
    #       1 so that the next nick change will be broadcasted.
