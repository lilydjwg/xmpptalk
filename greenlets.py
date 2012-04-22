#
# (C) Copyright 2012 lilydjwg <lilydjwg@gmail.com>
#
# This file is part of xmpptalk.
#
# xmpptalk is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# xmpptalk is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with xmpptalk.  If not, see <http://www.gnu.org/licenses/>.
#
import logging

from greenlet import greenlet

import config
import models
from misc import *

logger = logging.getLogger(__name__)
nick_paths = ('{vcard-temp}vCard/{vcard-temp}FN', '{vcard-temp}vCard/{vcard-temp}N/FAMILY')

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
      for path in nick_paths:
        nickel = stanza.as_xml().find(path)
        if nickel:
          nick = nickel.text
          if nick:
            break
      else:
        nick = s.get_name(jid)
        logger.warn('failed to get nick from vCard: %r', stanza.as_xml())

    while s.nick_exists(nick):
      nick += '_'
    try:
      models.validate_nick(nick)
    except models.ValidationError:
      nick = hashjid(jid)

    msg = _('Your nick is default to "%s", '\
            'you can use "%snick new_nick" to choose another.') % (
      nick, config.prefix
    )
    s.send_message(jid, msg)
    s.set_user_nick(str(jid.bare()), nick, increase=False)
    logger.info('%s joined with nick %s', jid, nick)
