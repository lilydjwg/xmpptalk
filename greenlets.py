import logging

from greenlet import greenlet

import config
import models
from misc import *

logger = logging.getLogger(__name__)

class Welcome(greenlet):
  def __init__(self, jid, xmpp, use_roster_nick=False):
    '''
    `jid` is a full `JID`, `xmpp` is the bot itself

    `use_roster_nick` indicates if roster nick (or hashed jid) is preferred
    because the user has alreadly joined but not in database
    '''
    super().__init__()
    self.switch(jid, xmpp, use_roster_nick)

  def run(self, jid, s, use_roster_nick):
    s.send_message(jid, config.welcome)
    s.get_vcard(jid, self.switch)
    stanza = self.parent.switch()
    if use_roster_nick or stanza.stanza_type == 'error':
      nick = s.get_name(jid)
    else:
      nick = stanza.get_all_payload()[0].element.find('{vcard-temp}FN').text
      while s.nick_exists(nick):
        nick += '_'
    try:
      models.validate_nick(nick)
    except models.ValidationError:
      nick = hashjid(jid)

    msg = _('Would you like to use "%s" as your nick, '\
            'or use "%snick your_nick" to choose another') % (
      nick, config.user_default_prefix
    )
    s.send_message(jid, msg)
    s.set_user_nick(str(jid.bare()), nick, increase=False)
    logger.info('%s joined with nick %s', jid, nick)
