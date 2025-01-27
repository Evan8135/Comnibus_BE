import globals
import bcrypt

users = globals.db.users

# CREATING THE ADMIN USER
admin_user_list = [
    {
        "name" : "Page Master",
        "username": "pagemaster1",
        "password": b"Agamemnon",
        "email": "evan8135@gmail.com",
        "admin": True
    }
]
for admin_user in admin_user_list:
    admin_user["password"] = bcrypt.hashpw(admin_user["password"], bcrypt.gensalt())
    users.insert_one(admin_user)
