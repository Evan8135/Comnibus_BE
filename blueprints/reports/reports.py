from flask import Blueprint, jsonify, make_response, request
from bson import ObjectId
from bson.regex import Regex
from datetime import datetime
from aggregation import user_score_aggregation
from decorators import jwt_required, admin_required, author_required
import globals
from blueprints.messages.messages import send_message

reports_bp = Blueprint("reports_bp", __name__)
books = globals.db.books
thoughts = globals.db.thoughts
reports = globals.db.reports

# REPORT APIS
#------------------------------------------------------------------------------------------------------------------
@reports_bp.route("/api/v1.0/reports", methods=["GET"])
@jwt_required
@admin_required
def get_all_reports():
    all_reports = []

    for report in reports.find():
        report['_id'] = str(report['_id'])
        report['reported_at'] = report['reported_at'].isoformat()
        all_reports.append(report)

    return make_response(jsonify(all_reports), 200)


@reports_bp.route("/api/v1.0/reports/<string:report_id>", methods=["GET"])
@jwt_required
@admin_required
def get_one_report(report_id):
    report = reports.find_one({"_id": ObjectId(report_id)})

    if not report:
        return make_response(jsonify({"error": "Report not found"}), 404)

    report['_id'] = str(report['_id'])
    report['reported_at'] = report['reported_at'].isoformat() 

    return make_response(jsonify(report), 200)

@reports_bp.route("/api/v1.0/reports/<string:report_id>/approve", methods=["POST"])
@jwt_required
@admin_required
def approve_report(report_id):
    token_data = request.token_data
    reporter_username = token_data['username']

    report = reports.find_one({"_id": ObjectId(report_id)})

    if not report:
        return make_response(jsonify({"error": "Report not found"}), 404)

    reported_id = ObjectId(report['item_id'])
    report_type = report['type']

    review_user = None
    reply_user = None
    thought_user = None
    thought_reply_user = None

    update_result = None

    if report_type == 'review':
        book_id = ObjectId(report['book_id'])
        user_score = user_score_aggregation(book_id)

        review = books.find_one(
            {"_id": book_id, "user_reviews._id": reported_id},
            {"user_reviews.$": 1}
        )
        if review and review.get("user_reviews"):
            review_user = review["user_reviews"][0]["username"]

        update_result = books.update_one(
            {"_id": book_id},
            {"$pull": {"user_reviews": {"_id": reported_id}}}
        )

        books.update_one({"_id": book_id}, {"$set": {"user_score": user_score}})

    elif report_type == 'review reply':
        book_id = ObjectId(report['book_id'])

        parent_review = books.find_one(
            {"_id": book_id, "user_reviews.replies._id": reported_id},
            {"user_reviews.$": 1}
        )
        if parent_review and parent_review.get("user_reviews"):
            replies = parent_review['user_reviews'][0].get('replies', [])
            for reply in replies:
                if reply['_id'] == reported_id:
                    reply_user = reply['username']
                    break

        update_result = books.update_one(
            {"_id": book_id, "user_reviews._id": parent_review['user_reviews'][0]['_id']},
            {"$pull": {"user_reviews.$.replies": {"_id": reported_id}}}
        )

    elif report_type == 'thought':
        thought = thoughts.find_one({"_id": reported_id})
        if thought:
            thought_user = thought["username"]
            update_result = thoughts.delete_one({"_id": reported_id})
        else:
            return make_response(jsonify({"error": "Thought not found"}), 404)

    elif report_type == 'thought reply':
        thought_id = ObjectId(report['thought_id'])

        thought = thoughts.find_one(
            {"_id": thought_id, "replies._id": reported_id},
            {"replies.$": 1}
        )
        if thought and thought.get("replies"):
            thought_reply_user = thought["replies"][0]["username"]

        update_result = thoughts.update_one(
            {"_id": thought_id},
            {"$pull": {"replies": {"_id": reported_id}}}
        )
    else:
        return make_response(jsonify({"error": "Invalid report type"}), 400)

    if isinstance(update_result, dict):
        operation_count = update_result.get('modified_count', 0)
    elif hasattr(update_result, 'modified_count'):
        operation_count = update_result.modified_count
    elif hasattr(update_result, 'deleted_count'):
        operation_count = update_result.deleted_count
    else:
        operation_count = 0

    if operation_count == 0:
        return make_response(jsonify({"error": f"{report_type.capitalize()} not found or already removed"}), 404)

    send_message(
        recipient_name=reporter_username,
        content=f"Thank you for your report! After reviewing it, we have determined that the {report_type} has indeed violated our community guidelines and we have removed it."
    )

    if review_user:
        send_message(
            recipient_name=review_user,
            content="Your review has been removed because it violated our community guidelines."
        )
    if reply_user:
        send_message(
            recipient_name=reply_user,
            content="Your reply to a review has been removed because it violated our community guidelines."
        )
    if thought_user:
        send_message(
            recipient_name=thought_user,
            content="Your thought has been removed because it violated our community guidelines."
        )
    if thought_reply_user:
        send_message(
            recipient_name=thought_reply_user,
            content="Your reply to a thought has been removed because it violated our community guidelines."
        )

    reports.delete_one({"_id": ObjectId(report_id)})

    return make_response(jsonify({"message": f"{report_type.capitalize()} and report deleted successfully"}), 200)




@reports_bp.route("/api/v1.0/reports/<string:report_id>/reject", methods=["POST"])
@jwt_required
@admin_required
def reject_report(report_id):
    token_data = request.token_data
    reporter_username = token_data['username']

    report = reports.find_one({"_id": ObjectId(report_id)})

    if not report:
        return make_response(jsonify({"error": "Report not found"}), 404)

    report_type = report['type']
    
    send_message(
        recipient_name=reporter_username,
        content=f"Thank you for your report! After reviewing it, we have determined that the {report_type} does not violate our community guidlines and will not be removed."
    )

    reports.delete_one({"_id": ObjectId(report_id)})

    return make_response(jsonify({"message": "Report deleted successfully"}), 200)

@reports_bp.route("/api/v1.0/reports/<string:report_id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_report(report_id):
    result = reports.delete_one({"_id": ObjectId(report_id)})

    if result.deleted_count == 0:
        return make_response(jsonify({"error": "Report not found"}), 404)

    return make_response(jsonify({"message": "Report deleted successfully"}), 200)