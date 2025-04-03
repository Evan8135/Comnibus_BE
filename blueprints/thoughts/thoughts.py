from flask import Blueprint, request, make_response, jsonify
from bson import ObjectId
from datetime import datetime
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
        'created_at': datetime.utcnow(),
        'replies': []
    }

    new_thought_id = thoughts.insert_one(posted_thought)

    new_thoughts_link = f"http://localhost:4200/api/v1.0/thoughts/{new_thought_id.inserted_id}"
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
        thought_info = {
            "_id": thought['_id'],
            "username": thought['username'],
            "comment": thought['comment'],
            "likes": thought['likes'],
            "dislikes": thought['dislikes'],
            'created_at': thought['created_at'],
            "replies": thought['replies']
        }
        for reply in thought['replies']:
            reply['_id'] = str(reply['_id'])
        
        all_thoughts.append(thought_info)
    return make_response(jsonify(all_thoughts), 200)

@thoughts_bp.route("/api/v1.0/thoughts/<string:id>", methods=["GET"])
@jwt_required
def show_one_thought(id):
    thought = thoughts.find_one({'_id': ObjectId(id)})
    if thought:
        thought['_id'] = str(thought['_id'])
    else:
        return make_response(jsonify({"error": "Invalid thought ID"}), 404)
    
    thought['_id'] = str(thought['_id'])
    for reply in thought['replies']:
        reply['_id'] = str(reply['_id'])
    return make_response(jsonify(thought), 200)
    
@thoughts_bp.route("/api/v1.0/thoughts/<string:id>/like", methods=["POST"])
@jwt_required
def like_thought(id):
    token_data = request.token_data
    liker_username = token_data['username']

    thought = thoughts.find_one({"_id": ObjectId(id)})
    if not thought:
        return make_response(jsonify({"error": "Thought not found"}), 404)

    # Increment likes
    result = thoughts.update_one(
        {"_id": ObjectId(id)},
        {"$inc": {"likes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid thought ID"}), 400)

    recipient_username = thought.get("username")
    print("Recipient username:", recipient_username)  # Debugging log

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

    thought = thoughts.find_one({"_id": ObjectId(id)})
    if not thought:
        return make_response(jsonify({"error": "Thought not found"}), 404)

    # Increment dislikes
    result = thoughts.update_one(
        {"_id": ObjectId(id)},
        {"$inc": {"dislikes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid thought ID"}), 400)

    recipient_username = thought.get("username")
    print("Recipient username:", recipient_username)  # Debugging log

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
    
@thoughts_bp.route("/api/v1.0/thoughts/<string:id>", methods=["DELETE"]) 
@jwt_required
def delete_thought(id):
    token_data = request.token_data
    current_user = token_data['username']
    admin = token_data.get('admin', False)

    # Find the book and the specific review to delete
    thought = thoughts.find_one(
        {"_id": ObjectId(id)}
    )

    if not thought:
        return make_response(jsonify({"error": "Thought not found"}), 404)


    thought_username = thought.get("username")

    # Check if the user is authorized to delete the review
    if not admin and thought_username != current_user:
        return make_response(jsonify({"error": "Unauthorized to delete this thought"}), 403)

    result = thoughts.delete_one({"_id":ObjectId(id)})
    if result.deleted_count == 1:
        return make_response(jsonify({}), 204)
    else:
        return make_response(jsonify({"error": "Invalid request ID"}), 404)



@thoughts_bp.route("/api/v1.0/thoughts/<string:id>/replies", methods=["POST"])
@jwt_required
def reply_to_thought(id):
    token_data = request.token_data
    username = token_data['username']  # USERNAME FROM LOGIN IS FILLED IN AUTOMATICALLY

    # Validate the input data
    content = request.form.get('content')

    if not content:
        return make_response(jsonify({"error": "Please put something in."}), 400)
    
    

    added_reply = {
        '_id': ObjectId(),
        'username': username,
        'content': content,
        'created_at': datetime.utcnow(),
        'likes': 0,  # Initialize likes count
        'dislikes': 0  # Initialize dislikes count
    }

    # Add the reply to the thought's replies array
    thoughts.update_one(
        {"_id": ObjectId(id)},
        {"$push": {"replies": added_reply}}
    )



    # Return the URL for the new reply
    new_reply_link = f"http://localhost:5000/api/v1.0/thoughts/" + id + "/replies/" + str(added_reply['_id'])
    return make_response(jsonify({"url": new_reply_link}), 201)


@thoughts_bp.route("/api/v1.0/thoughts/<string:id>/replies", methods=["GET"])
def show_all_replys(id):
    all_replys = []
    thought = thoughts.find_one({"_id": ObjectId(id)}, {"replies": 1, "_id": 0})
    replies = thought.get('replies', ())


    for reply in replies:
        reply['_id'] = str(reply['_id'])
        all_replys.append(reply)

    return make_response(jsonify(all_replys), 200)



@thoughts_bp.route("/api/v1.0/thoughts/<string:thought_id>/replies/<string:reply_id>", methods=["GET"])
def get_one_reply(thought_id, reply_id):
    thought = thoughts.find_one( { "_id": ObjectId(thought_id), "replies._id": ObjectId(reply_id) }, 
                            { "_id" : 1, "replies.$" : 1 } )
    if thought is None:
        return make_response( jsonify( { "error" : "Invalid Review ID" } ), 400 )
    reply = thought['replies'][0]
    reply['_id'] = str(reply["_id"])
    reply['thought_id'] = str(thought['_id'])

    
    return make_response( jsonify( thought["replies"][0] ), 200 )





@thoughts_bp.route("/api/v1.0/thoughts/<string:thought_id>/replies/<string:reply_id>/like", methods=["POST"])
@jwt_required
def like_reply(thought_id, reply_id):
    token_data = request.token_data
    liker_username = token_data['username']

    # Check if the review exists and get the review details
    thought = thoughts.find_one(
        {"_id": ObjectId(thought_id), "replies._id": ObjectId(reply_id)},
        {"replies.$": 1}
    )
    

    if not thought or "replies" not in thought:
        return make_response(jsonify({"error": "Reply not found"}), 404)

    reply = thought["replies"][0]
    recipient_username = reply.get("username")

    # Check if the liker is trying to like their own review
    if liker_username == recipient_username:
        return make_response(jsonify({"error": "You cannot like your own replies"}), 400)

    # Increment the like count for the review
    result = thoughts.update_one(
        {"_id": ObjectId(thought_id), "replies._id": ObjectId(reply_id)},
        {"$inc": {"replies.$.likes": 1}}
    )

    if result.matched_count == 0:
        return make_response(jsonify({"error": "Invalid Reply ID"}), 400)

    # Send a notification to the recipient that their review was liked
    if recipient_username:
        send_message(
            recipient_name=recipient_username,
            content=f"{liker_username} liked your Reply!"
        )

    return make_response(jsonify({"message": "Reply liked successfully"}), 200)

    
@thoughts_bp.route("/api/v1.0/thoughts/<string:thought_id>/replies/<string:reply_id>", methods=["DELETE"]) 
@jwt_required
def delete_review(thought_id, reply_id):
    token_data = request.token_data
    current_user = token_data['username']
    admin = token_data.get('admin', False)

    # Find the book and the specific review to delete
    thought = thoughts.find_one(
        {"_id": ObjectId(thought_id), "replies._id": ObjectId(reply_id)},
        {"replies.$": 1}
    )

    if not thought or "replies" not in thought:
        return make_response(jsonify({"error": "Review not found"}), 404)

    reply = thought["replies"][0]
    reply_username = reply.get("username")

    # Check if the user is authorized to delete the review
    if not admin and reply_username != current_user:
        return make_response(jsonify({"error": "Unauthorized to delete this review"}), 403)

    # Remove the review from the book
    thoughts.update_one({ "_id" : ObjectId(thought_id) }, { "$pull" : { "replies" : { "_id" : ObjectId(reply_id) } } })
    
    
    return make_response(jsonify({}), 204)