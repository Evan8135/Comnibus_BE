from flask import Blueprint, request, make_response, jsonify
import jwt
from datetime import datetime, timedelta, timezone
import bcrypt
import globals
from decorators import jwt_required, admin_required
from bson import ObjectId
from blueprints.messages.messages import send_message

auth_bp = Blueprint("auth_bp", __name__)

blacklist = globals.db.blacklist
users = globals.db.users
books = globals.db.books
thoughts = globals.db.thoughts
banned_emails = globals.db.banned_emails
deleted_accounts = globals.db.deleted_accounts

# AUTH APIS
#------------------------------------------------------------------------------------------------------------------
# 1. BASIC REGISTRATION FEATURES
@auth_bp.route('/api/v1.0/signup', methods=["POST"])
def signup():
    name = request.form.get('name')
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    pronouns = request.form.get('pronouns')
    user_type = request.form.get('user_type')
    favourite_genres = request.form.get('favourite_genres')
    favourite_authors = request.form.get('favourite_authors')
    admin = request.form.get('admin', False)

    current_time = datetime.utcnow()

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
        'pronouns': pronouns,
        'user_type': user_type,
        'favourite_genres': favourite_genres.split(",") if favourite_genres else [],
        'favourite_authors': favourite_authors.split(",") if favourite_authors else [],
        'favourite_books': [],
        'profile_pic': '',
        'followers': [],
        'following': [],
        'have_read': [],
        'want_to_read': [],
        'currently_reading': [],
        'awards': [],
        'admin': admin,
        'created_at': current_time,
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
            suspension_end_date = user.get('suspension_end_date')
            if suspension_end_date:
                if suspension_end_date.tzinfo is None:
                    suspension_end_date = suspension_end_date.replace(tzinfo=timezone.utc)
                
            if suspension_end_date and datetime.now(timezone.utc) < suspension_end_date:
                remaining_days = (suspension_end_date - datetime.now(timezone.utc)).days
                return make_response(jsonify({'message': 'Account is suspended. Come back in ' + str(remaining_days) +' days'}), 403)
            if bcrypt.checkpw(bytes(auth.password, 'UTF-8'), user["password"]):
                token = jwt.encode( {
                    'name': user['name'],
                    'username': auth.username,
                    'admin': user['admin'],
                    'followers': user['followers'],
                    'user_type': user['user_type'],
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

def serialize_user(user):
    """ Convert ObjectId fields to string """
    user['_id'] = str(user['_id'])
    return user


#------------------------------------------------------------------------------------------------------------------
# 2. USER CRUD FEATURES
@auth_bp.route('/api/v1.0/users', methods=["GET"])
def show_all_users():
    page_num, page_size = 1, 10
    search_username = request.args.get('username')

    query = {}
    if search_username:
        query["username"] = {"$regex": search_username, "$options": "i"}

    users_list = list(users.find(query, {'password': 0}))

    for user in users_list:
        user['_id'] = str(user['_id'])

    return make_response(jsonify(users_list), 200)




@auth_bp.route("/api/v1.0/users/<string:id>", methods=["GET"])
def show_one_user(id):
    user = users.find_one({"_id": ObjectId(id)}, {"password": 0})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)
    
    user["_id"] = str(user["_id"])
    
    reviews_by_user = []
    books_by_author = []
    
    if user.get("user_type") == "author":
        for book in books.find({"author": user["name"]}):
            book["_id"] = str(book["_id"])
            books_by_author.append(book)

    for book in books.find({"user_reviews.username": user["username"]}):
        for review in book.get("user_reviews", []):
            if review.get("username") == user["username"]:
                review["_id"] = str(review["_id"])
                review["book_id"] = str(book["_id"])
                review["book_title"] = book["title"]
                reviews_by_user.append(review)
    
    response_data = {
        "user": user,
        "books_by_author": books_by_author,
        "reviews_by_user": reviews_by_user
    }
    
    return make_response(jsonify(response_data), 200)

@auth_bp.route("/api/v1.0/users/<string:id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_user(id):
    result = users.delete_one({"_id":ObjectId(id)})
    if result.deleted_count == 1:
        return make_response(jsonify({}), 204)
    else:
        return make_response(jsonify({"error": "Invalid user ID"}), 404)
    


#------------------------------------------------------------------------------------------------------------------
# 3. FOLLOW FEATURES
@auth_bp.route('/api/v1.0/users/<string:id>/follow', methods=["POST"])
@jwt_required
def follow_user(id):
    token_data = request.token_data
    username = token_data['username']

    user_to_follow = users.find_one({"_id": ObjectId(id)}, {"password": 0})
    if not user_to_follow:
        return make_response(jsonify({"error": "User to follow not found"}), 404)

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    if id == str(user["_id"]):
        return make_response(jsonify({"error": "You cannot follow yourself"}), 400)

    following_data = {
        "_id": id,
        "username": user_to_follow["username"]
    }
    
    follower_data = {
        "_id": str(user["_id"]),
        "username": username
    }

    if any(f["username"] == user_to_follow["username"] for f in user.get("following", [])):
        return make_response(jsonify({"message": "Already following this user"}), 400)

    users.update_one({"_id": user["_id"]}, {"$push": {"following": following_data}})

    users.update_one({"_id": user_to_follow["_id"]}, {"$push": {"followers": follower_data}})

    return make_response(jsonify({"message": f"Successfully followed {user_to_follow['username']}"}), 200)


@auth_bp.route('/api/v1.0/users/<string:id>/unfollow', methods=["POST"])
@jwt_required
def unfollow_user(id):
    token_data = request.token_data
    username = token_data['username']

    user_to_unfollow = users.find_one({"_id": ObjectId(id)})
    if not user_to_unfollow:
        return make_response(jsonify({"error": "User to unfollow not found"}), 404)

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    if id == str(user["_id"]):
        return make_response(jsonify({"error": "You cannot unfollow yourself"}), 400)

    if id not in user["following"]:
        return make_response(jsonify({"message": "You are not following this user"}), 400)

    users.update_one({"_id": user["_id"]}, {"$pull": {"following": id}})
    users.update_one({"_id": user_to_unfollow["_id"]}, {"$pull": {"followers": user["_id"]}})

    return make_response(jsonify({"message": f"Successfully unfollowed {user_to_unfollow['username']}"}), 200)

#------------------------------------------------------------------------------------------------------------------
# 3.5. DELETE FOLLOW FEATURES FOR TESTING
@auth_bp.route('/api/v1.0/remove-all-followers', methods=["POST"])
@jwt_required
def remove_all_followers():
    token_data = request.token_data
    username = token_data['username']

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    users.update_one({"_id": user["_id"]}, {"$set": {"followers": []}})

    for follower in user['followers']:
        users.update_one({"_id": ObjectId(follower['id'])}, {"$pull": {"following": user["_id"]}})

    return make_response(jsonify({"message": "All followers removed successfully"}), 200)

@auth_bp.route('/api/v1.0/remove-all-following', methods=["POST"])
@jwt_required
def remove_all_following():
    token_data = request.token_data
    username = token_data['username']

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    users.update_one({"_id": user["_id"]}, {"$set": {"following": []}})

    for follower in user['followers']:
        users.update_one({"_id": ObjectId(follower['id'])}, {"$pull": {"following": user["_id"]}})

    return make_response(jsonify({"message": "All followers removed successfully"}), 200)


#------------------------------------------------------------------------------------------------------------------
# 4. USER FEED FEATURES
@auth_bp.route('/api/v1.0/feed', methods=["GET"])
@jwt_required
def user_feed():
    token_data = request.token_data
    username = token_data['username']
    
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    following_list = user.get("following", [])
    if not following_list:
        return make_response(jsonify({"message": "You are not following anyone."}), 200)

    following_ids = [ObjectId(f["_id"]) for f in following_list]
    feed_activities = []

    def parse_timestamp(ts):
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return datetime.min  
        return ts if isinstance(ts, datetime) else datetime.min


    reviews_by_user = []
    for book in books.find({"user_reviews.username": username}):
        for review in book.get("user_reviews", []):
            if review.get("username") == username:
                reviews_by_user.append({
                    "activity_type": "reviewed",
                    "username": "You",
                    "book_id": str(book["_id"]),
                    "book_title": book["title"],
                    "review_id": str(review["_id"]),
                    "review_content": review["comment"],
                    "timestamp": review.get("created_at", datetime.now().isoformat())
                })

    feed_activities.extend(reviews_by_user)

    review_replies_by_user = []
    for book in books.find({"user_reviews.username": username}):
        for review in book.get("user_reviews", []):
            for review_reply in review.get("replies", []):
                if review_reply.get("username") == username:
                    review_replies_by_user.append({
                        "activity_type": "replied to a review by",
                        "username": "You",
                        "review_user": review["username"],
                        "book_id": str(book["_id"]),
                        "review_id": str(review["_id"]),
                        "reply_id": str(review_reply["_id"]),
                        "reply_content": review_reply["content"],
                        "timestamp": review_reply.get("created_at", datetime.now().isoformat())
                    })
    feed_activities.extend(review_replies_by_user)

    thoughts_by_user = []
    for thought in thoughts.find({"username": username}):
        if thought.get("username") == username:
            thoughts_by_user.append({
                "activity_type": "posted a thought",
                "username": "You",
                "thought_id": str(thought["_id"]),
                "thought_content": thought["comment"],
                "timestamp": thought.get("created_at", datetime.now().isoformat())
            })

    feed_activities.extend(thoughts_by_user)

    replies_by_user = []
    for thought in thoughts.find({"replies.username": username}):
        for reply in thought.get("replies", []):
            if reply.get("username") == username:
                replies_by_user.append({
                    "activity_type": "replied to a thought by",
                    "username": "You",
                    "thought_id": str(thought["_id"]),
                    "thought_user": thought["username"],
                    "reply_content": reply["content"],
                    "timestamp": reply.get("created_at", datetime.now().isoformat())
                })

    feed_activities.extend(replies_by_user)

    for book in user.get("currently_reading", []):
        progress = book.get('progress', 0)
        activity = {
            "activity_type": "Started Reading" if progress == 0 else "Reading Progress",
            "username": "You",
            "book_title": book.get("title", "Unknown Title"),
            "progress": f"{progress}%",
            "current_page": f"{book.get('current_page', 0)} / {book.get('total_pages', 0)}",
            "timestamp": book.get("reading_time", datetime.now().isoformat())
        }
        feed_activities.append(activity)

    for book in user.get("have_read", []):
        rating = book.get('stars')
        activity = {
            "activity_type": "Finished Reading",
            "username": "You",
            "book_title": book.get("title", "Unknown Title"),
            "rating": f"{rating}",
            "timestamp": book.get("date_read", datetime.now().isoformat())
        }
        feed_activities.append(activity)

    for followed_user in users.find({"_id": {"$in": following_ids}}):
        followed_username = followed_user["username"]

        for book in books.find({"user_reviews.username": followed_username}):
            for review in book.get("user_reviews", []):
                if review.get("username") == followed_username:
                    feed_activities.append({
                        "activity_type": "reviewed",
                        "username": followed_username,
                        "book_id": str(book["_id"]),
                        "book_title": book["title"],
                        "review_id": str(review["_id"]),
                        "review_content": review["comment"],
                        "timestamp": review.get("created_at", datetime.now())
                    })

        for book in books.find({"user_reviews.username": followed_username}):
            for review in book.get("user_reviews", []):
                for review_reply in review.get("replies", []):
                    if review_reply.get("username") == followed_username:
                        feed_activities.append({
                            "activity_type": "replied to a review by",
                            "username": followed_username,
                            "review_user": review["username"],
                            "book_id": str(book["_id"]),
                            "review_id": str(review["_id"]),
                            "review_reply_id": str(review_reply["_id"]),
                            "review_reply_content": review_reply["content"],
                            "timestamp": review_reply.get("created_at", datetime.now().isoformat())
                        })


        
        for thought in thoughts.find({"username": followed_username}):
            if thought.get("username") == username:
                thoughts_by_user.append({
                    "activity_type": "posted a thought",
                    "username": followed_username,
                    "thought_content": thought["comment"],
                    "timestamp": thought.get("created_at", datetime.now().isoformat())
                })

        for thought in thoughts.find({"replies.username": followed_username}):
            for reply in thought.get("replies", []):
                if reply.get("username") == followed_username:
                    feed_activities.append({
                        "activity_type": "replied to a thought by",
                        "username": followed_username,
                        "thought_id": str(thought["_id"]),
                        "thought_user": thought["username"],
                        "reply_content": reply["content"],
                        "timestamp": reply.get("created_at", datetime.now())
                    })


        # Add reading progress for followed user
        for book in followed_user.get("currently_reading", []):
            progress = book.get('progress', 0)
            activity = {
                "activity_type": "Started Reading" if progress == 0 else "Reading Progress",
                "username": followed_username,
                "book_title": book.get("title", "Unknown Title"),
                "progress": f"{progress}%",
                "current_page": f"{book.get('current_page', 0)} / {book.get('total_pages', 0)}",
                "timestamp": book.get("reading_time", datetime.now().isoformat())
            }
            feed_activities.append(activity)

        for book in followed_user.get("have_read", []):
            rating = book.get('stars')
            activity = {
                "activity_type": "Finished Reading",
                "username": followed_username,
                "book_title": book.get("title", "Unknown Title"),
                "rating": f"{rating}",
                "timestamp": book.get("date_read", datetime.now().isoformat())
            }
            feed_activities.append(activity)

    # Sort all activities by timestamp in reverse order (most recent first)
    feed_activities.sort(key=lambda x: parse_timestamp(x["timestamp"]), reverse=True)

    # Return the combined feed activities
    return make_response(jsonify({"feed": feed_activities}), 200)

#------------------------------------------------------------------------------------------------------------------
# 5. USER PROFILE FEATURES
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
    
@auth_bp.route('/api/v1.0/profile', methods=['PUT'])
@jwt_required
def edit_profile():
    token_data = request.token_data
    username = token_data['username']
    
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    data = request.get_json()
    
    updates = {}

    if "name" in data:
        updates["name"] = data["name"]
    if "username" in data and data["username"] != user["username"]:
        if users.find_one({"username": data["username"]}):
            return make_response(jsonify({"error": "Username already taken"}), 409)
        updates["username"] = data["username"]
    if "email" in data and data["email"] != user["email"]:
        if users.find_one({"email": data["email"]}):
            return make_response(jsonify({"error": "Email already in use"}), 409)
        updates["email"] = data["email"]
    if "pronouns" in data and data["pronouns"] != user["pronouns"]:
        updates["pronouns"] = data["pronouns"]
    if "favourite_genres" in data:
        updates["favourite_genres"] = data["favourite_genres"]
    if "favourite_authors" in data:
        updates["favourite_authors"] = data["favourite_authors"]
    if "profile_pic" in data:
        profile_pic_url = data["profile_pic"]

        if not profile_pic_url: 
            updates["profile_pic"] = ""
        
        if profile_pic_url.startswith("blob:"):
            return make_response(jsonify({"error": "Temporary blob URL is not allowed. Please upload a permanent image URL."}), 400)
        
        updates["profile_pic"] = profile_pic_url


    users.update_one({"username": username}, {"$set": updates})

    return make_response(jsonify({"message": "Profile updated successfully"}), 200)

@auth_bp.route('/api/v1.0/delete-account', methods=["DELETE"])
@jwt_required
def delete_own_account():
    token_data = request.token_data
    username = token_data['username']
    
    reason = request.form.get('reason', 'No reason provided')

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Save the reason for deletion (optional so we can use user feedback)
    deletion_log = {
        "username": username,
        "reason": reason,
        "timestamp": datetime.utcnow()
    }
    deleted_accounts.insert_one(deletion_log)

    # Delete user from the database
    result = users.delete_one({"_id": user["_id"]})
    
    if result.deleted_count == 1:
        # Add the token to the blacklist to log the user out
        token = request.headers.get('x-access-token')
        blacklist.insert_one({"token": token})
        
        return make_response(jsonify({"message": "Your account has been deleted and you have been logged out.", "reason": reason}), 200)
    else:
        return make_response(jsonify({"error": "Failed to delete account"}), 500)

#------------------------------------------------------------------------------------------------------------------
# 5.5. USER PROFILE FEATURES (FOR TESTING)
@auth_bp.route('/api/v1.0/remove-all-authors', methods=["POST"])
@jwt_required
def remove_all_favourite_authors():
    token_data = request.token_data
    username = token_data['username']

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    users.update_one({"_id": user["_id"]}, {"$set": {"favourite_authors": []}})

    return make_response(jsonify({"message": "All authors removed successfully"}), 200)


@auth_bp.route('/api/v1.0/remove-profile-pic', methods=['POST'])
@jwt_required
def remove_profile_pic():
    token_data = request.token_data
    username = token_data['username']

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    users.update_one({"username": username}, {"$set": {"profile_pic": ""}})

    return make_response(jsonify({"message": "Profile picture removed successfully"}), 200)


    
#------------------------------------------------------------------------------------------------------------------
# 5. USER VIOLATION FEATURES
@auth_bp.route('/api/v1.0/users/<user_id>/suspend', methods=["POST"])
@jwt_required
@admin_required
def suspend_user(user_id):
    suspension_length = 7
    suspension_end_date = datetime.now(timezone.utc) + timedelta(days=suspension_length)
    results = users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "suspension_end_date": suspension_end_date}}
    )

    if results.modified_count == 1:
        return make_response(jsonify({'message': "User has been suspended "}), 201)
    else:
        return make_response(jsonify({"error": "Invalid User ID"}), 404)
    

@auth_bp.route('/api/v1.0/users/<user_id>/ban', methods=["POST"])
@jwt_required
@admin_required
def ban_user(user_id):
    result = users.find_one( { "_id" : ObjectId(user_id) } )
    banned_user = users.delete_one( { "_id" : ObjectId(user_id) } )
    if banned_user.deleted_count == 1:
        email = result.get('email')
        banned_emails.insert_one({"emails": email}) # THEIR EMAIL IS ADDED TO THE BANNED EMAILS COLLECTION
        return make_response(jsonify({"message": "User has been banned"}), 201)
    else:
        return make_response(jsonify({"error": "Invalid User ID"}), 404)
    
