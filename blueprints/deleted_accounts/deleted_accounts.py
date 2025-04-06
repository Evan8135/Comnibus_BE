from flask import Blueprint, jsonify, make_response, request
from bson import ObjectId
from bson.regex import Regex
from datetime import datetime
from aggregation import user_score_aggregation
from decorators import jwt_required, admin_required, author_required
import globals
from blueprints.messages.messages import send_message

deleted_accounts_bp = Blueprint("deleted_accounts_bp", __name__)
deleted_accounts = globals.db.deleted_accounts

# DELETED ACCOUNT APIS
#------------------------------------------------------------------------------------------------------------------
@deleted_accounts_bp.route("/api/v1.0/user-feedback", methods=["GET"])
@jwt_required
@admin_required
def get_all_feedback():
    all_deleted_accounts = []

    for deleted_account in deleted_accounts.find():
        deleted_account['_id'] = str(deleted_account['_id'])
        all_deleted_accounts.append(deleted_account)

    return make_response(jsonify(all_deleted_accounts), 200)


@deleted_accounts_bp.route("/api/v1.0/deleted-accounts/<string:deleted_account_id>", methods=["GET"])
@jwt_required
@admin_required
def get_one_deleted_account(deleted_account_id):
    deleted_account = deleted_accounts.find_one({"_id": ObjectId(deleted_account_id)})

    if not deleted_account:
        return make_response(jsonify({"error": "deleted_account not found"}), 404)

    deleted_account['_id'] = str(deleted_account['_id'])
    deleted_account['timestamp'] = deleted_account['timestamp'].isoformat() 

    return make_response(jsonify(deleted_account), 200)

@deleted_accounts_bp.route("/api/v1.0/deleted-accounts/<string:deleted_account_id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_deleted_account(deleted_account_id):
    result = deleted_accounts.delete_one({"_id": ObjectId(deleted_account_id)})

    if result.deleted_count == 0:
        return make_response(jsonify({"error": "deleted_account not found"}), 404)

    return make_response(jsonify({"message": "deleted_account deleted successfully"}), 200)