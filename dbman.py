import models
models.init()

from models import connection
from models import User, Log
import config

def setup_user_collection():
  col = connection[User.__database__][User.__collection__]
  User.generate_index(col)

def setup_log_collection():
  db = connection[Log.__database__]
  #http://www.mongodb.org/display/DOCS/Capped+Collections
  db.create_collection(Log.__collection__, {
    'capped': True,
    'size': getattr(config, 'log_size', 524288),
  })

if __name__ == '__main__':
  setup_user_collection()
  setup_log_collection()
