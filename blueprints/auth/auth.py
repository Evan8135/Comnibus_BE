from flask import Blueprint, request, make_response, jsonify
import jwt
from datetime import datetime, timedelta, timezone
import bcrypt
import globals
from decorators import jwt_required, admin_required
from bson import ObjectId

auth_bp = Blueprint("auth_bp", __name__)

blacklist = globals.db.blacklist
users = globals.db.users
#banned_emails = globals.db.banned_emails

#@auth_bp.route('/api/v1.0/signup', methods=["POST"])
#def signup():
#    name = request.form.get('name')
#    username = request.form.get('username')
#    password = request.form.get('email')
#    user_type = request.form.get('user_type')
#    favourite_genres = request.form.get('favourite_genres')
#    admin = request.form.get('admin', False)

@auth_bp.route('/api/v1.0/login', methods=['GET'])
def login():
    auth = request.authorization
    if auth:
        user = users.find_one({'username': auth.username})
        if user is not None:
            #suspension_end_date = user.get('suspension_end_date')
            #if suspension_end_date:
            #    if suspension_end_date.tzinfo is None:
            #        suspension_end_date = suspension_end_date.replace(tzinfo=timezone.utc)
                
            #if suspension_end_date and datetime.now(timezone.utc) < suspension_end_date:
            #    remaining_days = (suspension_end_date - datetime.now(timezone.utc)).days
            #    return make_response(jsonify({'message': 'Account is suspended. Come back in ' + str(remaining_days) +' days'}), 403)
            if bcrypt.checkpw(bytes(auth.password, 'UTF-8'), user["password"]):
                token = jwt.encode( {
                    'username': auth.username,
                    'admin': user['admin'],
                    'exp': datetime.now(timezone.utc) + timedelta(hours=1) }, globals.secret_key, algorithm="HS256")
                return make_response(jsonify({'token': token}), 200)
            else:
                return make_response(jsonify({'message': 'Incorrect Password'}), 401, {
                        'WWW-Authenticate':  'Basic realm="Login Required"'
                })
                
        else:
            return make_response(jsonify({'message': 'Incorrect Username'}), 401, {
                        'WWW-Authenticate':  'Basic realm="Login Required"'
                })
    return make_response(jsonify( {'message': 'Login Required'}), 401, {
                        'WWW-Authenticate':  'Basic realm="Login Required"'
                })


@auth_bp.route('/api/v1.0/logout', methods=["GET"])
@jwt_required
def logout():
    token = request.headers['x-access-token']
    blacklist.insert_one({"token": token})
    return make_response(jsonify({'message' : 'Logout Successful'}), 200)

# ADMINS WILL BE ABLE TO SEE ALL USERS
@auth_bp.route('/api/v1.0/users', methods=["GET"])
@jwt_required
@admin_required
def show_all_users():
    all_users = list(users.find({}, {'password': 0}))
    for user in all_users:
        user['_id'] = str(user['_id'])
    return make_response(jsonify(all_users), 200)



@auth_bp.route("/api/v1.0/users/<string:id>", methods=["GET"])
@jwt_required
@admin_required
def show_one_user(id):
    user = users.find_one({"_id": ObjectId(id)}, {"password": 0})
    if user:
        user["_id"] = str(user["_id"])
        return make_response(jsonify(user), 200)
    else:
        return make_response(jsonify({"error": "User not found"}), 404)