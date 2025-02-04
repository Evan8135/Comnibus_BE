from flask import Blueprint, request, jsonify, make_response
from bson import ObjectId
import datetime
from decorators import jwt_required
import globals

messages_bp = Blueprint("messages_bp", __name__)
messages = globals.db.messages
users = globals.db.users



@messages_bp.route("/api/v1.0/inbox", methods=["GET"])
@jwt_required
def get_messages():
    token_data = request.token_data
    username = token_data['username']
    user_messages = messages.find({"recipient_name": username})
    messages_list = [{
        "_id": str(message["_id"]),
        "recipient_name": username,
        "content": message["content"],
        "timestamp": message["timestamp"],
        "is_read": message.get("is_read", False)
    } for message in user_messages]
    has_unread = any(not msg["is_read"] for msg in messages_list)
    response = {
        "messages": messages_list,
        "hasUnreadMessages": has_unread
    }
    
    return make_response(jsonify(response), 200)

def send_message( content, recipient_name):
    message = { 
        "recipient_name": recipient_name,
        "content": content,
        "timestamp": datetime.datetime.now(datetime.UTC),
        "is_read": False
    }
    messages.insert_one(message)

@messages_bp.route("/api/v1.0/inbox/<string:id>", methods=["GET"])
@jwt_required
def show_one_message(id):
    one_message = messages.find_one( { '_id' : ObjectId(id) } )
    if one_message is not None:
        one_message['_id'] = str( one_message['_id'] )
        return make_response( jsonify( one_message ), 200 )
    else:
        return make_response( jsonify( { "error" : "Invalid Message ID" } ), 404 )

@messages_bp.route("/api/v1.0/inbox/<message_id>/read", methods=["PUT"])
@jwt_required
def mark_as_read(message_id):
    messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"is_read": True}}
    )
    return jsonify({"message": "Message marked as read"}), 200


@messages_bp.route("/api/v1.0/inbox/<string:id>", methods=["DELETE"])
@jwt_required
def delete_message(id):
    result = messages.delete_one({"_id":ObjectId(id)})
    if result.deleted_count == 1:
        return make_response(jsonify({}), 204)
    else:
        return make_response(jsonify({"error": "Invalid Message ID"}), 404)