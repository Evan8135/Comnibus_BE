from flask import request, jsonify, make_response
import jwt
from functools import wraps
import globals

blacklist = globals.db.blacklist

def jwt_required(func):
    @wraps(func)
    def jwt_required_wrapper(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            return make_response( jsonify( { 'message' : 'Token is Missing' } ), 401 )
        try:
            data = jwt.decode( token, globals.secret_key, algorithms="HS256" )
            request.token_data = data
        except:
            return make_response( jsonify( { 'message' : 'Token is invalid' } ), 401 )
        bl_token = blacklist.find_one({"token":token})
        if bl_token is not None:
            return make_response(jsonify( {'message' : 'Token has been cancelled'} ), 401 )
        return func(*args, **kwargs)
    return jwt_required_wrapper

def admin_required(func):
    @wraps(func)
    def admin_required_wrapper(*args, **kwargs):
        token = request.headers['x-access-token']
        data = jwt.decode(token, globals.secret_key, algorithms="HS256")
        if data["admin"]:
            return func(*args, **kwargs)
        else:
            return make_response(jsonify({'message': 'Admin access denied'}), 401)
    return admin_required_wrapper

def author_required(func):
    @wraps(func)
    def author_required_wrapper(*args, **kwargs):
        token = request.headers.get('x-access-token')

        if not token:
            return make_response(jsonify({'message': 'Token is missing'}), 403)
        
        try:
            data = jwt.decode(token, globals.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return make_response(jsonify({'message': 'Token has expired'}), 401)
        except jwt.InvalidTokenError:
            return make_response(jsonify({'message': 'Invalid token'}), 401)

        # Ensure the user_type field is handled correctly (author or admin)
        is_author = data.get("user_type") == "author"
        is_admin = data.get("admin") == "true" or data.get("admin") is True

        if is_author or is_admin:  # Check if the user is an author or admin
            return func(*args, **kwargs)
        else:
            return make_response(jsonify({'message': 'Author access denied'}), 403)
    
    return author_required_wrapper

