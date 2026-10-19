import sys

from mysite.db.database import SessionLocal
from mysite.db.models import UserProfile, UserRole

if len(sys.argv) != 2:
    sys.exit("usage: python create_admin.py <username>")

db = SessionLocal()
try:
    user = db.query(UserProfile).filter(UserProfile.username == sys.argv[1]).first()
    if not user:
        sys.exit("user not found")
    user.role = UserRole.admin
    db.commit()
    print(f"{user.username} is now admin")
finally:
    db.close()
