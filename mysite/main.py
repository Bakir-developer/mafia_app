from fastapi import FastAPI
from mysite.api import user_profile, auth
from mysite.admin.setup import setup_admin

app = FastAPI(title='Mafia_app')
app.include_router(user_profile.user_router)
app.include_router(auth.auth_router)

setup_admin(app)