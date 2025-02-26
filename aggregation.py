from bson import ObjectId
import globals

books = globals.db.books

def user_score_aggregation(book_id): 
    pipeline = [ 
        { 
            "$match": {"_id": ObjectId(book_id)} 
        }, 
        { 
            "$unwind": "$user_reviews" 
        }, 
        { 
            "$group": { 
                "_id": "$_id", 
                "total_reviews": {"$sum": 1}, 
                "positive_reviews": { 
                    "$sum": { 
                        "$cond": [{"$gte": ["$user_reviews.stars", 3]}, 1, 0] 
                    } 
                } 
            } 
        },
        { 
            "$project": { 
                "user_score": {
                    "$cond": {
                        "if": {"$eq": ["$total_reviews", 0]},  # If there are no reviews
                        "then": 0,  # Set user score to 0
                        "else": {
                            "$round": [
                                { 
                                    "$multiply": [
                                        {"$divide": ["$positive_reviews", "$total_reviews"]},
                                        5  # Score out of 5
                                    ]
                                },
                                1
                            ]
                        }
                    }
                } 
            } 
        }
    ] 
    result = list(books.aggregate(pipeline)) 
    return result[0]['user_score'] if result else 0  # Ensure user score is 0 if no reviews exist
