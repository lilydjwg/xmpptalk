import re

# for i18n support
_ = lambda s: s

PERM_USER = 1
PERM_GPADMIN = 2
PERM_SYSADMIN = 4

re_jid = re.compile(r'[^@ ]+@(?:\w+\.)+\w{2,4}')

__all__ = list(globals().keys())
