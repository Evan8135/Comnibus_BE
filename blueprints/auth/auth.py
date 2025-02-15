from flask import Blueprint, request, make_response, jsonify
import jwt
from datetime import datetime, timedelta, timezone
import bcrypt
import globals
from decorators import jwt_required, admin_required
from bson import ObjectId
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from blueprints.messages.messages import send_message

auth_bp = Blueprint("auth_bp", __name__)

blacklist = globals.db.blacklist
users = globals.db.users
books = globals.db.books
banned_emails = globals.db.banned_emails

@auth_bp.route('/api/v1.0/signup', methods=["POST"])
def signup():
    name = request.form.get('name')
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    user_type = request.form.get('user_type')
    favourite_genres = request.form.get('favourite_genres')
    favourite_authors = request.form.get('favourite_authors')
    admin = request.form.get('admin', False)

    if not name or not username or not password or not email or not user_type:
        return make_response(jsonify({'message': 'Incomplete user information'}))
    
    if users.find_one({'username': username}) or users.find_one({'email': email}):
        return make_response({jsonify({'message': 'This User is already on COMNIBUS'}), 409})
    
    if banned_emails.find_one({'emails': email}):
        return make_response(jsonify({'message': 'This email is banned'}), 409)
    
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    new_user = {
        'name': name,
        'username': username,
        'email': email,
        'password': hashed_password,
        'user_type': user_type,
        'favourite_genres': favourite_genres.split(",") if favourite_genres else [],
        'favourite_authors': favourite_authors.split(",") if favourite_authors else [],
        'favourite_books': [],
        'followers': [],
        'following': [],
        'have_read': [],
        'want_to_read': [],
        'currently_reading': [],
        'admin': admin,
        'suspension_end_date': None
    }

    users.insert_one(new_user)
    send_message(
        recipient_name=username,
        content=f"Dear {name}, Welcome to COMNIBUS, a humble book website made by readers for readers.\nYou can now access some of the features we have to offer such as: \n1. Write book reviews \n2. Catalogue the books you are reading \n3. Follow your friends and like minded readers \n These are but a few of the features with more on the way. \nHappy Browsing, \nThe Team at COMNIBUS"
    )
    return make_response(jsonify({'message': 'User has been created'}), 201)

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


@auth_bp.route('/api/v1.0/users', methods=["GET"])
#@jwt_required
def show_all_users():
    page_num, page_size = 1, 10
    search_username = request.args.get('username')

    query = {}
    if search_username:
        query["username"] = {"$regex": search_username, "$options": "i"}

    users_list = list(users.find(query, {'password': 0}))  # Exclude passwords

    # Convert ObjectId to string
    for user in users_list:
        user['_id'] = str(user['_id'])

    return make_response(jsonify(users_list), 200)




@auth_bp.route("/api/v1.0/users/<string:id>", methods=["GET"])
#@jwt_required
def show_one_user(id):
    user = users.find_one({"_id": ObjectId(id)}, {"password": 0})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    user["_id"] = str(user["_id"])
    
    reviews_by_user = []
    for book in books.find({"user_reviews.username": user["username"]}):
        for review in book.get("user_reviews", []):
            if review.get("username") == user["username"]:
                review["_id"] = str(review["_id"])
                review["book_id"] = str(book["_id"])
                review["book_title"] = book["title"]
                reviews_by_user.append(review)
    
    response_data = {
        "user": user,
        "reviews_by_user": reviews_by_user
    }
    
    return make_response(jsonify(response_data), 200)

    
@auth_bp.route("/api/v1.0/profile", methods=["GET"])
@jwt_required
def show_profile():
    token_data = request.token_data
    username = token_data['username']
    user = users.find_one({"username": username}, {"password": 0})
    if user:
        user["_id"] = str(user["_id"])
        return make_response(jsonify(user), 200)
    else:
        return make_response(jsonify({"error": "User not found"}), 404)
    
