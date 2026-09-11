import os
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')

ACCESS_EXPIRE_TOKEN=int(os.getenv('ACCESS_EXPIRE_TOKEN'))
REFRESH_EXPIRE_TOKEN=int(os.getenv('REFRESH_EXPIRE_TOKEN'))
ALGORITHM=os.getenv('ALGORITHM')