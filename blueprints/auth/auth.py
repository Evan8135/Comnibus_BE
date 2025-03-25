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

def serialize_user(user):
    """ Convert ObjectId fields to string """
    user['_id'] = str(user['_id'])
    return user


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


    
    
@auth_bp.route('/api/v1.0/users/<string:id>/follow', methods=["POST"])
@jwt_required
def follow_user(id):
    token_data = request.token_data
    username = token_data['username']

    # Fetch the user to follow
    user_to_follow = users.find_one({"_id": ObjectId(id)}, {"password": 0})
    if not user_to_follow:
        return make_response(jsonify({"error": "User to follow not found"}), 404)

    # Fetch the current user
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    if id == str(user["_id"]):  # Ensure users cannot follow themselves
        return make_response(jsonify({"error": "You cannot follow yourself"}), 400)

    # Create follow data objects
    following_data = {
        "_id": id,
        "username": user_to_follow["username"]
    }
    
    follower_data = {
        "_id": str(user["_id"]),
        "username": username
    }

    # Check if already following
    if any(f["username"] == user_to_follow["username"] for f in user.get("following", [])):
        return make_response(jsonify({"message": "Already following this user"}), 400)

    # Update `following` for the current user
    users.update_one({"_id": user["_id"]}, {"$push": {"following": following_data}})

    # Update `followers` for the followed user
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

    # Check if the user is not following
    if id not in user["following"]:
        return make_response(jsonify({"message": "You are not following this user"}), 400)

    # Remove user from the following list of the current user and remove the current user from the followers list of the other user
    users.update_one({"_id": user["_id"]}, {"$pull": {"following": id}})
    users.update_one({"_id": user_to_unfollow["_id"]}, {"$pull": {"followers": user["_id"]}})

    return make_response(jsonify({"message": f"Successfully unfollowed {user_to_unfollow['username']}"}), 200)

@auth_bp.route('/api/v1.0/feed', methods=["GET"])
@jwt_required
def user_feed():
    token_data = request.token_data
    username = token_data['username']
    
    # Fetch the user document
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    following_list = user.get("following", [])
    if not following_list:
        return make_response(jsonify({"message": "You are not following anyone."}), 200)

    following_ids = [ObjectId(f["_id"]) for f in following_list]
    feed_activities = []

    # Helper function to parse timestamps correctly
    def parse_timestamp(ts):
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return datetime.min  # Default to the oldest possible if parsing fails
        return ts if isinstance(ts, datetime) else datetime.min


    # Add the logged-in user's activities to the feed
    reviews_by_user = []
    for book in books.find({"user_reviews.username": username}):
        for review in book.get("user_reviews", []):
            if review.get("username") == username:
                reviews_by_user.append({
                    "activity_type": "Reviewed",
                    "username": "You",
                    "book_id": str(book["_id"]),
                    "book_title": book["title"],
                    "review_id": str(review["_id"]),
                    "review_content": review["comment"],
                    "timestamp": review.get("created_at", datetime.now().isoformat())
                })

    feed_activities.extend(reviews_by_user)

    thoughts_by_user = []
    for thought in thoughts.find({"username": username}):
        if thought.get("username") == username:
            thoughts_by_user.append({
                "activity_type": "Posted a Thought",
                "username": "You",
                "thought_content": thought["comment"],
                "timestamp": thought.get("created_at", datetime.now().isoformat())
            })

    feed_activities.extend(thoughts_by_user)

    replies_by_user = []
    for thought in thoughts.find({"replies.username": username}):
        for reply in thought.get("replies", []):
            if reply.get("username") == username:
                replies_by_user.append({
                    "activity_type": "Replied to",
                    "username": "You",
                    "thought_user": thought["username"],
                    "reply_content": reply["content"],
                    "timestamp": reply.get("created_at", datetime.now().isoformat())
                })

    feed_activities.extend(replies_by_user)

    # Add the user's reading progress to the feed
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

    # Add activities for each followed user
    for followed_user in users.find({"_id": {"$in": following_ids}}):
        followed_username = followed_user["username"]

        # Get recent reviews for followed user
        for book in books.find({"user_reviews.username": followed_username}):
            for review in book.get("user_reviews", []):
                if review.get("username") == followed_username:
                    feed_activities.append({
                        "activity_type": "Reviewed",
                        "username": followed_username,
                        "book_id": str(book["_id"]),
                        "book_title": book["title"],
                        "review_id": str(review["_id"]),
                        "review_content": review["comment"],
                        "timestamp": review.get("created_at", datetime.now())
                    })
        
        for thought in thoughts.find({"username": followed_username}):
            if thought.get("username") == username:
                thoughts_by_user.append({
                    "activity_type": "Posted a Thought",
                    "username": followed_username,
                    "thought_content": thought["comment"],
                    "timestamp": thought.get("created_at", datetime.now().isoformat())
                })

        for thought in thoughts.find({"replies.username": followed_username}):
            for reply in thought.get("replies", []):
                if reply.get("username") == followed_username:
                    feed_activities.append({
                        "activity_type": "Replied to",
                        "username": followed_username,
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

    # Sort all activities by timestamp in reverse order (most recent first)
    feed_activities.sort(key=lambda x: parse_timestamp(x["timestamp"]), reverse=True)

    # Return the combined feed activities
    return make_response(jsonify({"feed": feed_activities}), 200)




@auth_bp.route('/api/v1.0/remove-all-followers', methods=["POST"])
@jwt_required
def remove_all_followers():
    token_data = request.token_data
    username = token_data['username']

    # Retrieve the user from the database
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Remove all followers from the user's followers list
    users.update_one({"_id": user["_id"]}, {"$set": {"followers": []}})

    # Optionally, you may want to remove the user from the followers lists of those who were following them
    for follower in user['followers']:
        users.update_one({"_id": ObjectId(follower['id'])}, {"$pull": {"following": user["_id"]}})

    return make_response(jsonify({"message": "All followers removed successfully"}), 200)

@auth_bp.route('/api/v1.0/remove-all-following', methods=["POST"])
@jwt_required
def remove_all_following():
    token_data = request.token_data
    username = token_data['username']

    # Retrieve the user from the database
    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Remove all followers from the user's followers list
    users.update_one({"_id": user["_id"]}, {"$set": {"following": []}})

    # Optionally, you may want to remove the user from the followers lists of those who were following them
    for follower in user['followers']:
        users.update_one({"_id": ObjectId(follower['id'])}, {"$pull": {"following": user["_id"]}})

    return make_response(jsonify({"message": "All followers removed successfully"}), 200)




    
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

    # Get form data
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

        if not profile_pic_url:  # If it's an empty string (""), handle accordingly
            updates["profile_pic"] = ""
        
        # If you want to make sure the profile pic is a permanent URL (not a blob URL)
        if profile_pic_url.startswith("blob:"):
            return make_response(jsonify({"error": "Temporary blob URL is not allowed. Please upload a permanent image URL."}), 400)
        
        updates["profile_pic"] = profile_pic_url
    #if "password" in data:
    #    hashed_password = bcrypt.hashpw(data["password"].encode('utf-8'), bcrypt.gensalt())
    #    updates["password"] = hashed_password

    users.update_one({"username": username}, {"$set": updates})

    return make_response(jsonify({"message": "Profile updated successfully"}), 200)

@auth_bp.route('/api/v1.0/remove-profile-pic', methods=['POST'])
@jwt_required
def remove_profile_pic():
    token_data = request.token_data
    username = token_data['username']

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found"}), 404)

    # Set the profile picture field to null or default image URL
    users.update_one({"username": username}, {"$set": {"profile_pic": ""}})

    return make_response(jsonify({"message": "Profile picture removed successfully"}), 200)


    
@auth_bp.route("/api/v1.0/users/<string:id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_request(id):
    result = users.delete_one({"_id":ObjectId(id)})
    if result.deleted_count == 1:
        return make_response(jsonify({}), 204)
    else:
        return make_response(jsonify({"error": "Invalid user ID"}), 404)