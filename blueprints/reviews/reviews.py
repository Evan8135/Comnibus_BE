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
reports = globals.db.reports
MAX_REVIEWS_PER_WEEK = 3 # Each user can only post 3 reviews a week
MIN_ACCOUNT_AGE_DAYS = 3 # Each user needs to wait 3 days after signing up before they can add a review


# REVIEWS APIS
#------------------------------------------------------------------------------------------------------------------
# 1. BASIC REVIEW FEATURES
@reviews_bp.route("/api/v1.0/books/<string:id>/reviews", methods=["POST"])
@jwt_required
def add_new_review(id):
    token_data = request.token_data
    username = token_data['username']  # USERNAME FROM LOGIN IS FILLED IN AUTOMATICALLY

    current_time = datetime.utcnow()
    start_of_week = current_time - timedelta(days=current_time.weekday())

    user = users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"error": "User not found."}), 400)
    
    account_creation_date = user.get("created_at")
    if (current_time - account_creation_date).days < MIN_ACCOUNT_AGE_DAYS:
        return make_response(jsonify({"error": f"Your account must be at least 3 days old to post reviews."}), 400)

    reviews_by_user = []
    for book in books.find({"user_reviews.username": username}):
        for review in book.get("user_reviews", []):
            if review.get("username") == username:
                review["_id"] = str(review["_id"])
                review["book_id"] = str(book["_id"])
                review["book_title"] = book["title"]
                reviews_by_user.append(review)

    user_reviews_this_week = [
        review for review in reviews_by_user
        if review["created_at"] >= start_of_week
    ]

    review_count = sum(1 for _ in user_reviews_this_week)
    
    if review_count >= MAX_REVIEWS_PER_WEEK:
        return make_response(jsonify({"error": f"You can only post {MAX_REVIEWS_PER_WEEK} reviews per week."}), 400)

    existing_review = books.find_one(
        {"_id": ObjectId(id), "user_reviews.username": username}
    )
    if existing_review:
        return make_response(jsonify({"error": "You have already reviewed this book."}), 400)

    title = request.form.get('title', '')
    comment = request.form.get('comment')
    stars = float(request.form.get('stars'))

    if not comment or not stars:
        return make_response(jsonify({"error": "Title, comment, and stars are required."}), 400)

    added_review = {
        '_id': ObjectId(),
        'username': username,
        'title': title,
        'comment': comment,
        'stars': stars,
        'likes': 0,  
        'dislikes': 0, 
        'created_at': current_time,
        'updated_at': current_time,
        'replies': []
    }

    books.update_one(
        {"_id": ObjectId(id)},
        {"$push": {"user_reviews": added_review}}
    )

    user_score = user_score_aggregation(id)
    books.update_one({"_id": ObjectId(id)}, {"$set": {"user_score": user_score}})

    new_review_link = f"http://localhost:5000/api/v1.0/books/{id}/reviews/{str(added_review['_id'])}"
    return make_response(jsonify({"url": new_review_link}), 201)



@reviews_bp.route("/api/v1.0/books/<string:id>/reviews", methods=["GET"])
def show_all_reviews(id):
    all_reviews = []
    book = books.find_one({"_id": ObjectId(id)}, {"user_reviews": 1})
    user_reviews = book.get('user_reviews', ())


    for review in user_reviews:
        review['_id'] = str(review['_id'])
        all_reviews.append(review)
        for reply in review['replies']:
            reply['_id'] = str(reply['_id'])
        

    return make_response(jsonify(all_reviews), 200)

@reviews_bp.route("/api/v1.0/review/<string:review_id>", methods=["GET"])
def get_one_review(review_id):
    book = books.find_one(
        {"user_reviews._id": ObjectId(review_id)},
        {"_id": 1, "user_reviews.$": 1}
    )

    if book is None:
        return make_response(jsonify({"error": "Invalid Review ID"}), 400)

    review = book["user_reviews"][0]
    review["_id"] = str(review["_id"])
    review["book_id"] = str(book["_id"])
    for reply in review['replies']:
        reply['_id'] = str(reply['_id'])

    return make_response(jsonify(review), 200)


@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>/like", methods=["POST"])
@jwt_required
def like_review(book_id, review_id):
    token_data = request.token_data
    liker_username = token_data['username']

    book = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"user_reviews.$": 1}
    )

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    recipient_username = review.get("username")

    if liker_username == recipient_username:
        return make_response(jsonify({"error": "You cannot like your own review"}), 400)

    result = books.update_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"$inc": {"user_reviews.$.likes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid Review ID"}), 400)

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

    book = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"user_reviews.$": 1}
    )

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    recipient_username = review.get("username")

    if disliker_username == recipient_username:
        return make_response(jsonify({"error": "You cannot dislike your own review"}), 400)

    result = books.update_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"$inc": {"user_reviews.$.dislikes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid Review ID"}), 400)

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

    book = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"user_reviews.$": 1}
    )

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    review_username = review.get("username")

    if not admin and review_username != current_user:
        return make_response(jsonify({"error": "Unauthorized to delete this review"}), 403)

    books.update_one({ "_id" : ObjectId(book_id) }, { "$pull" : { "user_reviews" : { "_id" : ObjectId(review_id) } } })
    
    user_score = user_score_aggregation(book_id)
    books.update_one({"_id": ObjectId(book_id)}, {"$set": {"user_score": user_score}})

    return make_response(jsonify({}), 204)

#------------------------------------------------------------------------------------------------------------------
# 2. REPLY FEATURES
@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>/replies", methods=["POST"])
@jwt_required
def reply_to_review(book_id, review_id):
    token_data = request.token_data
    username = token_data['username']

    content = request.form.get('content')
    if not content:
        return make_response(jsonify({"error": "Please provide a reply content."}), 400)

    added_reply = {
        '_id': ObjectId(),
        'username': username,
        'content': content,
        'created_at': datetime.utcnow(),
        'likes': 0,
        'dislikes': 0
    }

    result = books.update_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"$push": {"user_reviews.$.replies": added_reply}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Review not found"}), 404)

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
        reply['book_id'] = book_id
        reply['review_id'] = review_id 
        all_replies.append(reply)

    return make_response(jsonify(all_replies), 200)




@reviews_bp.route("/api/v1.0/review/<string:review_id>/replies/<string:reply_id>", methods=["GET"])
def get_one_reply(review_id, reply_id):
    result = books.find_one(
        {"user_reviews._id": ObjectId(review_id), "user_reviews.replies._id": ObjectId(reply_id)},
        {"_id": 0, "user_reviews.replies.$": 1} 
    )

    if not result or "user_reviews" not in result or not result["user_reviews"]:
        return make_response(jsonify({"error": "Invalid reply ID"}), 400)

    reply = result["user_reviews"][0]["replies"][0] 
    reply["_id"] = str(reply["_id"]) 

    return make_response(jsonify(reply), 200)



@reviews_bp.route("/api/v1.0/review/<string:review_id>/replies/<string:reply_id>/like", methods=["POST"])
@jwt_required
def like_reply(review_id, reply_id):
    token_data = request.token_data
    liker_username = token_data['username']

    review = books.find_one(
        {"user_reviews._id": ObjectId(review_id), "user_reviews.replies._id": ObjectId(reply_id)},
        {"user_reviews.$": 1}
    )

    if not review or not review.get("user_reviews"):
        return make_response(jsonify({"error": "Review not found"}), 404)

    user_reviews = review["user_reviews"]
    reply = None
    for r in user_reviews:
        reply = next((rep for rep in r.get("replies", []) if str(rep["_id"]) == reply_id), None)
        if reply:
            break

    if not reply:
        return make_response(jsonify({"error": "Reply not found"}), 404)

    recipient_username = reply.get("username")

    if liker_username == recipient_username:
        return make_response(jsonify({"message": "You cannot like your own review"}), 403)

    result = books.update_one(
        {"user_reviews._id": ObjectId(review_id), "user_reviews.replies._id": ObjectId(reply_id)},
        {"$inc": {"user_reviews.$.replies.$[reply].likes": 1}},
        array_filters=[{"reply._id": ObjectId(reply_id)}]
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid reply ID"}), 400)

    if recipient_username:
        send_message(
            recipient_name=recipient_username,
            content=f"{liker_username} liked your reply!"
        )

    return make_response(jsonify({"message": "Reply liked successfully"}), 200)


#------------------------------------------------------------------------------------------------------------------
# 3. REPORT FEATURES
@reviews_bp.route("/api/v1.0/review/<string:review_id>/report", methods=["POST"])
@jwt_required
def report_review(review_id):
    token_data = request.token_data
    reporter_username = token_data['username']

    reason = request.form.get('reason')
    if not reason:
        return make_response(jsonify({"error": "Please provide a reason for the report."}), 400)

    book = books.find_one(
        {"user_reviews._id": ObjectId(review_id)},
        {"_id": 1, "user_reviews.$": 1}
    )


    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]

    report = {
        "_id": ObjectId(),
        "type": "review",
        "item_id": str(review_id),
        "book_id": str(book["_id"]),
        "reported_by": reporter_username,
        "reason": reason,
        "reported_at": datetime.utcnow(),
        "status": "pending", 
        "details": {
            "review": {
                "username": review["username"],
                "title": review.get("title"),
                "comment": review.get("comment"),
                "stars": review.get("stars"),
            }
        }
    }
    

    reports.insert_one(report)

    send_message(
        recipient_name=report['reported_by'],
        content=f"Your report will be reviewed by our admins to see if it violates our community guidlines"
    )
    

    return make_response(jsonify({"message": "Review reported successfully."}), 201)


@reviews_bp.route("/api/v1.0/review/<string:review_id>/replies/<string:reply_id>/report", methods=["POST"])
@jwt_required
def report_reply(review_id, reply_id):
    token_data = request.token_data
    reporter_username = token_data['username']

    reason = request.form.get('reason') or request.json.get('reason')
    if not reason:
        return make_response(jsonify({"error": "Please provide a reason for the report."}), 400)

    book = books.find_one(
        {"user_reviews._id": ObjectId(review_id)},
        {"_id": 1, "user_reviews.$": 1}
    )

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    reply = next((r for r in review.get("replies", []) if str(r["_id"]) == reply_id), None)

    if not reply:
        return make_response(jsonify({"error": "Reply not found"}), 404)

    report = {
        "_id": ObjectId(),
        "type": "review reply",
        "item_id": str(reply_id),
        "review_id": str(review_id),
        "book_id": str(book["_id"]),
        "reported_by": reporter_username,
        "reason": reason,
        "reported_at": datetime.utcnow(),
        "status": "pending",
        "details": {
            "reply": {
                "username": reply["username"],
                "content": reply.get("content"),
            }
        }
    }

    reports.insert_one(report)

    send_message(
        recipient_name=reporter_username,
        content=f"Your report will be reviewed by our admins to see if it violates our community guidlines"
    )

    return make_response(jsonify({"message": "Reply reported successfully."}), 201)

