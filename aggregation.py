from bson import ObjectId
import globals

books = globals.db.books

def user_score_aggregation(id): 
    pipeline = [ 
        { 
            "$match": {"_id": ObjectId(id)} 
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
                        "$cond": [{"$gte": [{"$toInt": "$user_reviews.stars"}, 3]}, 1, 0] 
                    } 
                } 
            } 
        }, 
        { 
            "$project": { 
                "user_score": { 
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
    ] 
    result = list(books.aggregate(pipeline)) 
    return result[0]['user_score'] if result else None
