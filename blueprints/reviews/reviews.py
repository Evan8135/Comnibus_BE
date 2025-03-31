from flask import Blueprint, request, make_response, jsonify
from bson import ObjectId
from decorators import jwt_required, admin_required
from datetime import datetime, timedelta
import globals
from aggregation import user_score_aggregation
from blueprints.messages.messages import send_message

reviews_bp = Blueprint("reviews_bp", __name__)

users = globals.db.users
books = globals.db.books
MAX_REVIEWS_PER_WEEK = 3
MIN_ACCOUNT_AGE_DAYS = 5

@reviews_bp.route("/api/v1.0/books/<string:id>/reviews", methods=["POST"])
@jwt_required
def add_new_review(id):
    token_data = request.token_data
    username = token_data['username']  # USERNAME FROM LOGIN IS FILLED IN AUTOMATICALLY

    # Get the current date and the start of the week
    current_time = datetime.utcnow()
    start_of_week = current_time - timedelta(days=current_time.weekday())  # Monday of the current week

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found."}), 400)
    
    account_creation_date = user.get("created_at")
    if (current_time - account_creation_date).days < MIN_ACCOUNT_AGE_DAYS:
        return make_response(jsonify({"error": f"Your account must be at least 5 days old to post reviews."}), 400)

    # Find reviews posted by the user in the current week
    reviews_by_user = []
    for book in books.find({"user_reviews.username": username}):
        for review in book.get("user_reviews", []):
            if review.get("username") == username:
                review["_id"] = str(review["_id"])
                review["book_id"] = str(book["_id"])
                review["book_title"] = book["title"]
                reviews_by_user.append(review)

    # Find reviews posted by the user in the current week from their profile's 'reviews_by_user' field
    user_reviews_this_week = [
        review for review in reviews_by_user
        if review["created_at"] >= start_of_week
    ]

    review_count = sum(1 for _ in user_reviews_this_week)
    
    # Check if the user has already posted the maximum number of reviews this week
    if review_count >= MAX_REVIEWS_PER_WEEK:
        return make_response(jsonify({"error": f"You can only post {MAX_REVIEWS_PER_WEEK} reviews per week."}), 400)

    # Check if the user has already reviewed this book
    existing_review = books.find_one(
        {"_id": ObjectId(id), "user_reviews.username": username}
    )
    if existing_review:
        return make_response(jsonify({"error": "You have already reviewed this book."}), 400)

    # Validate the input data
    title = request.form.get('title', '')
    comment = request.form.get('comment')
    stars = request.form.get('stars')

    if not comment or not stars:
        return make_response(jsonify({"error": "Title, comment, and stars are required."}), 400)

    # Create the new review
    added_review = {
        '_id': ObjectId(),
        'username': username,
        'title': title,
        'comment': comment,
        'stars': stars,
        'likes': 0,  # Initialize likes count
        'dislikes': 0,  # Initialize dislikes count
        'created_at': current_time,
        'updated_at': current_time,
        'replies': []
    }

    # Add the review to the book's user_reviews array
    books.update_one(
        {"_id": ObjectId(id)},
        {"$push": {"user_reviews": added_review}}
    )

    # Update user score based on the newly added review
    user_score = user_score_aggregation(id)
    books.update_one({"_id": ObjectId(id)}, {"$set": {"user_score": user_score}})

    # Return the URL for the new review
    new_review_link = f"http://localhost:5000/api/v1.0/books/{id}/reviews/{str(added_review['_id'])}"
    return make_response(jsonify({"url": new_review_link}), 201)



@reviews_bp.route("/api/v1.0/books/<string:id>/reviews", methods=["GET"])
def show_all_reviews(id):
    all_reviews = []
    book = books.find_one({"_id": ObjectId(id)}, {"user_reviews": 1, "_id": 0})
    user_reviews = book.get('user_reviews', ())


    for review in user_reviews:
        review['_id'] = str(review['_id'])
        all_reviews.append(review)

    return make_response(jsonify(all_reviews), 200)

@reviews_bp.route("/api/v1.0/review/<string:review_id>", methods=["GET"])
def get_one_review(review_id):
    book = books.find_one(
        {"user_reviews._id": ObjectId(review_id)},
        {"_id": 1, "user_reviews.$": 1}  # Include book _id in the result
    )

    if book is None:
        return make_response(jsonify({"error": "Invalid Review ID"}), 400)

    # Extract review and add book_id to the response
    review = book["user_reviews"][0]
    review["_id"] = str(review["_id"])  # Convert review ID to string
    review["book_id"] = str(book["_id"])  # Convert book ID to string
    for reply in review['replies']:
        reply['_id'] = str(reply['_id'])

    return make_response(jsonify(review), 200)





@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>/like", methods=["POST"])
@jwt_required
def like_review(book_id, review_id):
    token_data = request.token_data
    liker_username = token_data['username']

    # Check if the review exists and get the review details
    book = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"user_reviews.$": 1}
    )

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    recipient_username = review.get("username")

    # Check if the liker is trying to like their own review
    if liker_username == recipient_username:
        return make_response(jsonify({"error": "You cannot like your own review"}), 400)

    # Increment the like count for the review
    result = books.update_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"$inc": {"user_reviews.$.likes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid Review ID"}), 400)

    # Send a notification to the recipient that their review was liked
    if recipient_username:
        send_message(
            recipient_name=recipient_username,
            content=f"{liker_username} liked your review!"
        )

    return make_response(jsonify({"message": "Review liked successfully"}), 200)


    
@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>/dislike", methods=["POST"])
@jwt_required
def dislike_review(book_id, review_id):
    token_data = request.token_data
    disliker_username = token_data['username']

    # Check if the review exists and get the review details
    book = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"user_reviews.$": 1}
    )

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    recipient_username = review.get("username")

    # Check if the disliker is trying to dislike their own review
    if disliker_username == recipient_username:
        return make_response(jsonify({"error": "You cannot dislike your own review"}), 400)

    # Increment the dislike count for the review
    result = books.update_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"$inc": {"user_reviews.$.dislikes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid Review ID"}), 400)

    # Send a notification to the recipient that their review was disliked
    if recipient_username:
        send_message(
            recipient_name=recipient_username,
            content=f"{disliker_username} disliked your review!"
        )

    return make_response(jsonify({"message": "Review disliked successfully"}), 200)



@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>", methods=["DELETE"]) 
@jwt_required
def delete_review(book_id, review_id):
    token_data = request.token_data
    current_user = token_data['username']
    admin = token_data.get('admin', False)

    # Find the book and the specific review to delete
    book = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"user_reviews.$": 1}
    )

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    review_username = review.get("username")

    # Check if the user is authorized to delete the review
    if not admin and review_username != current_user:
        return make_response(jsonify({"error": "Unauthorized to delete this review"}), 403)

    # Remove the review from the book
    books.update_one({ "_id" : ObjectId(book_id) }, { "$pull" : { "user_reviews" : { "_id" : ObjectId(review_id) } } })
    
    # Recalculate the user score after deleting the review
    user_score = user_score_aggregation(book_id)  # Corrected to use book_id
    books.update_one({"_id": ObjectId(book_id)}, {"$set": {"user_score": user_score}})

    return make_response(jsonify({}), 204)


@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>/replies", methods=["POST"])
@jwt_required
def reply_to_review(book_id, review_id):
    token_data = request.token_data
    username = token_data['username']

    # Validate the input data
    content = request.form.get('content')
    if not content:
        return make_response(jsonify({"error": "Please provide a reply content."}), 400)

    added_reply = {
        '_id': ObjectId(),
        'username': username,
        'content': content,
        'created_at': datetime.utcnow(),
        'likes': 0,  # Initialize likes count
        'dislikes': 0  # Initialize dislikes count
    }

    # Add the reply to the review's replies array
    result = books.update_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"$push": {"user_reviews.$.replies": added_reply}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Review not found"}), 404)

    # Return the URL for the new reply
    new_reply_link = f"http://localhost:5000/api/v1.0/books/" + str(book_id) + "/reviews/" + str(review_id) + "/replies/" + str(added_reply['_id'])
    return make_response(jsonify({"url": new_reply_link}), 201)


@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>/replies", methods=["GET"])
def show_all_replies(book_id, review_id):
    all_replies = []
    book = books.find_one({"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)}, {"user_reviews.$": 1})

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    replies = review.get('replies', [])

    for reply in replies:
        reply['_id'] = str(reply['_id'])
        reply['book_id'] = book_id  # Include the book_id
        reply['review_id'] = review_id 
        all_replies.append(reply)

    return make_response(jsonify(all_replies), 200)




@reviews_bp.route("/api/v1.0/review/<string:review_id>/replies/<string:reply_id>", methods=["GET"])
def get_one_reply(review_id, reply_id):
    result = books.find_one(
        {"user_reviews._id": ObjectId(review_id), "user_reviews.replies._id": ObjectId(reply_id)},
        {"_id": 0, "user_reviews.replies.$": 1}  # Projection to get only the matching reply
    )

    if not result or "user_reviews" not in result or not result["user_reviews"]:
        return make_response(jsonify({"error": "Invalid reply ID"}), 400)

    reply = result["user_reviews"][0]["replies"][0]  # Correctly access the nested reply
    reply["_id"] = str(reply["_id"])  # Convert ObjectId to string

    return make_response(jsonify(reply), 200)



@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>/replies/<string:reply_id>/like", methods=["POST"])
@jwt_required
def like_reply(book_id, review_id, reply_id):
    token_data = request.token_data
    liker_username = token_data['username']

    # Increment the like count for the reply
    result = books.update_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id), "user_reviews.replies._id": ObjectId(reply_id)},
        {"$inc": {"user_reviews.$.replies.$[reply].likes": 1}},
        array_filters=[{"reply._id": ObjectId(reply_id)}]  # Specify which reply to increment
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid reply ID"}), 400)

    # Notify the recipient
    review = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id), "user_reviews.replies._id": ObjectId(reply_id)},
        {"user_reviews.$": 1}
    )

    reply = review["user_reviews"][0]["replies"][0]
    recipient_username = reply.get("username")

    if recipient_username:
        send_message(
            recipient_name=recipient_username,
            content=f"{liker_username} liked your reply!"
        )

    return make_response(jsonify({"message": "Reply liked successfully"}), 200)

