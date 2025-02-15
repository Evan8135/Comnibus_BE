from flask import Blueprint, request, make_response, jsonify
from bson import ObjectId
from decorators import jwt_required, admin_required
import globals
from aggregation import user_score_aggregation
from blueprints.messages.messages import send_message

reviews_bp = Blueprint("reviews_bp", __name__)

users = globals.db.users
books = globals.db.books

@reviews_bp.route("/api/v1.0/books/<string:id>/reviews", methods=["POST"])
@jwt_required
def add_new_review(id):
    token_data = request.token_data
    username = token_data['username']  # USERNAME FROM LOGIN IS FILLED IN AUTOMATICALLY

    added_review = {
        '_id': ObjectId(),
        'username': username,
        #'name': request.form['name'],
        'title': request.form['title'],  # Add title to the review
        'comment': request.form['comment'],
        'stars': float(request.form['stars']),
        'likes': 0,  # Initialize likes count
        'dislikes': 0  # Initialize dislikes count
    }

    books.update_one(
        {"_id": ObjectId(id)},
        {"$push": {"user_reviews": added_review}}
    )

    # Update user score based on the newly added review
    user_score = user_score_aggregation(id)
    books.update_one({"_id": ObjectId(id)}, {"$set": {"user_score": user_score}})

    new_review_link = "http://localhost:5000/api/v1.0/books/" + id + "/reviews/" + str(added_review['_id'])
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

@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>", methods=["GET"])
def get_one_review(book_id, review_id):
    book = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"_id": 0, "user_reviews.$": 1}
    )

    if book is None:
        return make_response(jsonify({"error": "Invalid Review ID"}), 400)

    book['user_reviews'][0]['_id'] = str(book['user_reviews'][0]['_id'])
    return make_response(jsonify(book["user_reviews"][0]), 200)

@reviews_bp.route("/api/v1.0/books/<string:book_id>/reviews/<string:review_id>/like", methods=["POST"])
@jwt_required
def like_review(book_id, review_id):
    token_data = request.token_data
    liker_username = token_data['username']

    result = books.update_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"$inc": {"user_reviews.$.likes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid Review ID"}), 400)

    book = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"user_reviews.$": 1}
    )

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    recipient_username = review.get("username")

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

    result = books.update_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"$inc": {"user_reviews.$.dislikes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid Review ID"}), 400)

    book = books.find_one(
        {"_id": ObjectId(book_id), "user_reviews._id": ObjectId(review_id)},
        {"user_reviews.$": 1}
    )

    if not book or "user_reviews" not in book:
        return make_response(jsonify({"error": "Review not found"}), 404)

    review = book["user_reviews"][0]
    recipient_username = review.get("username")

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

    # Check if the user is authorized to delete the review
    if not admin and review_username != current_user:
        return make_response(jsonify({"error": "Unauthorized to delete this review"}), 403)

    books.update_one({ "_id" : ObjectId(book_id) }, { "$pull" : { "user_reviews" : { "_id" : ObjectId(review_id) } } } )
    return make_response( jsonify( {} ), 204)
