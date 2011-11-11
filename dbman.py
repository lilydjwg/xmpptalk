from models import connection
from models import User

def setup_user_collection():
  col = connection[User.__database__][User.__collection__]
  User.generate_index(col)
