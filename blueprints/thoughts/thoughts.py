from flask import Blueprint, request, make_response, jsonify
from bson import ObjectId
from decorators import jwt_required, admin_required
import globals
from blueprints.messages.messages import send_message

thoughts_bp = Blueprint("thoughts_bp", __name__)

users = globals.db.users
thoughts = globals.db.thoughts

@thoughts_bp.route("/api/v1.0/thoughts", methods=["POST"])
@jwt_required
def post_thought():
    token_data = request.token_data
    username = token_data['username']  # USERNAME FROM LOGIN IS FILLED IN AUTOMATICALLY

    
    comment = request.form.get('comment')

    if not comment:
        return make_response(jsonify({"error": "Please fill in thought"}), 400)
    
    

    posted_thought = {
        '_id': ObjectId(),
        'username': username,
        'comment': comment,
        'likes': 0,  # Initialize likes count
        'dislikes': 0,  # Initialize dislikes count
        'replies': []
    }

    new_thought_id = thoughts.insert_one(posted_thought)

    new_thoughts_link = f"http://localhost:4200/api/v1.0/requests/{new_thought_id.inserted_id}"
    return make_response(jsonify({"url": new_thoughts_link}), 201)

@thoughts_bp.route("/api/v1.0/thoughts", methods=['GET'])
@jwt_required
def show_all_thoughts():
    page_num, page_size = 1, 20
    if request.args.get('pn'):
        page_num = int(request.args.get('pn'))
    if request.args.get('ps'):
        page_size = int(request.args.get('ps'))
    page_start = page_size * (page_num - 1)

    all_thoughts = []
    for thought in thoughts.find().skip(page_start).limit(page_size):
        thought['_id'] = str(thought['_id'])
        all_thoughts.append(all_thoughts)
    return make_response(jsonify(all_thoughts), 200)

@thoughts_bp.route("/api/v1.0/thoughts/<string:id>", methods=["GET"])
@jwt_required
def show_one_book_request(id):
    thought = thoughts.find_one({'_id': ObjectId(id)})
    if thought:
        thought['_id'] = str(thought['_id'])
        return make_response(jsonify(thought), 200)
    else:
        return make_response(jsonify({"error": "Invalid Book ID"}), 404)
    
@thoughts_bp.route("/api/v1.0/thoughts/<string:id>/like", methods=["POST"])
@jwt_required
def like_review(id):
    token_data = request.token_data
    liker_username = token_data['username']

    result = thoughts.update_one(
        {"_id": ObjectId(id)},
        {"$inc": {"thoughts.$.likes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid thought ID"}), 400)

    thought = thoughts.find_one(
        {"_id": ObjectId(id)},
        {"thoughts.$": 1}
    )

    if not thought:
        return make_response(jsonify({"error": "thought not found"}), 404)


    recipient_username = thought.get("username")

    if recipient_username:
        send_message(
            recipient_name=recipient_username,
            content=f"{liker_username} liked your thought!"
        )

    return make_response(jsonify({"message": "Thought liked successfully"}), 200)

    
@thoughts_bp.route("/api/v1.0/thoughts/<string:id>/dislike", methods=["POST"])
@jwt_required
def dislike_thought(id):
    token_data = request.token_data
    disliker_username = token_data['username']

    result = thoughts.update_one(
        {"_id": ObjectId(id)},
        {"$inc": {"thoughts.$.dislikes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid thought ID"}), 400)

    thought = thoughts.find_one(
        {"_id": ObjectId(id)},
        {"thoughts.$": 1}
    )

    if not thought:
        return make_response(jsonify({"error": "thought not found"}), 404)


    recipient_username = thought.get("username")

    if recipient_username:
        send_message(
            recipient_name=recipient_username,
            content=f"{disliker_username} disliked your thought!"
        )

    return make_response(jsonify({"message": "Thought disliked successfully"}), 200)

@thoughts_bp.route("/api/v1.0/thoughts/delete_all", methods=["DELETE"])
@jwt_required
@admin_required  # Ensure only admins can delete all thoughts
def delete_all_thoughts():
    result = thoughts.delete_many({})  # Delete all thoughts in the collection
    
    if result.deleted_count > 0:
        return make_response(jsonify({"message": f"{result.deleted_count} thoughts deleted successfully."}), 200)
    else:
        return make_response(jsonify({"error": "No thoughts found to delete."}), 404)
