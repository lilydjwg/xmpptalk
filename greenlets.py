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
    s.send_message(jid, s.welcome)
    s.get_vcard(jid, self.switch)
    stanza = self.parent.switch()
    if use_roster_nick or stanza.stanza_type == 'error':
      nick = s.get_name(jid)
    else:
      try:
        nick = stanza.as_xml.find('{vcard-temp}vCard/{vcard-temp}FN').text
        if nick is None:
          logger.warn('%s\'s vCard has a `None\' nick: %r', jid, stanza.as_xml)
          nick = s.get_name(jid)
      except AttributeError: #None
        nick = s.get_name(jid)

    while s.nick_exists(nick):
      nick += '_'
    try:
      models.validate_nick(nick)
    except models.ValidationError:
      nick = hashjid(jid)

    msg = _('Would you like to use "%s" as your nick, '\
            'or use "%snick your_nick" to choose another') % (
      nick, config.prefix
    )
    s.send_message(jid, msg)
    s.set_user_nick(str(jid.bare()), nick, increase=False)
    logger.info('%s joined with nick %s', jid, nick)
