from pymongo import MongoClient

secret_key = 'Moyola'

client = MongoClient("mongodb://127.0.0.1:27017")
db = client.comnibusDB