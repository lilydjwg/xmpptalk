from models import connection
from models import User

def create_user_collection(name):
  col = connection[name]
  User.generate_index(col)
