import re

# for i18n support
_ = lambda s: s

PERM_USER = 0b1
PERM_GPADMIN = 0b11
PERM_SYSADMIN = 0b101

MAX_MESSAGE_A_TIME = 10

re_jid = re.compile(r'[^@ ]+@(?:\w+\.)+\w{2,4}')

__all__ = list(globals().keys())
