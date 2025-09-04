from pymongo import MongoClient
from werkzeug.security import generate_password_hash
import json, os

client = MongoClient('mongodb://test:test@13.125.220.88',27017)
#client = MongoClient('localhost', 27017)
db = client.univ
base_path = os.path.dirname(__file__)
json_file = os.path.join(base_path, "static", "univData.json")

def Initialize():
    if db.univData.count_documents({})==0:
        with open(json_file,"r",encoding="utf-8") as f:
            univ_list = json.load(f)
        for univ in univ_list:
            db.univData.insert_one({"name":univ["university"],"career":univ["ratios"]["career"],"community":univ["ratios"]["community"],"academic":univ["ratios"]["academic"]})
    if db.user.count_documents({})==0:
        InsertUser("root", generate_password_hash('1234'))

def InsertTestStudentRecord():
    # This now inserts a complete document into the student_records collection.
    test_record = {
        "userIndex": 0,
        "main": {
            "1": {"career_aspiration": "웹툰 작가", "average_grade": "1.5"},
            "2": {"career_aspiration": "웹툰 작가", "average_grade": "1.2"},
            "3": {"career_aspiration": "게임 개발자", "average_grade": "1.0"}
        },
        "activities": {
            "schoolrec": "교내 예술제 및 미술 전시회 기획 및 운영",
            "classrec": "1인 1실천 프로젝트, 창의 탐구활동",
            "careerrec": "프리미어 프로 편집 특강, UI/UX 디자인 특강, 클레이 애니메이션 제작 프로젝트 참여",
            "clubrec": "어반 스케치, 업사이클링 디자인, 교내 벽화 제작 활동"
        },
        "specialty": [
            {"과목": "국어", "활동": "창작물 제작"}
        ]
    }
    db.student_records.update_one({"userIndex": 0}, {"$set": test_record}, upsert=True)

def HasStudentRecord(userIndex):
    record = db.student_records.find_one({'userIndex': userIndex})
    return record is not None and record.get('main') is not None and len(record.get('main')) > 0

def GetAllUniversities(): return list(db.univData.find({}, {'_id':0,'name':1}))
def GetUserById(id): return db.user.find_one({'id':id})
def HasId(id): return db.user.find_one({'id':id}) is not None

def InsertUser(id, pw):
    last_user = db.user.find_one(sort=[("userIndex",-1)])
    userIndex = 0 if last_user is None else last_user["userIndex"]+1
    db.user.insert_one({"id":id,"pw":pw,"userIndex":userIndex})
    # Create a corresponding empty student record
    db.student_records.insert_one({"userIndex": userIndex})
    return userIndex

def GetUniversityInfo(name): return db.univData.find_one({'name':name}, {'_id':0})

def GetStudentRecord(userIndex):
    # The student record is now the entire document in the new collection.
    record = db.student_records.find_one({'userIndex': userIndex})
    return record

def UpdateStudentRecord(userIndex, update_key, update_data):
    # This function now takes a specific key and data to update.
    db.student_records.update_one(
        {"userIndex": userIndex},
        {"$set": {update_key: update_data}},
        upsert=True
    )

def DeleteSpecialtyItem(userIndex, subject, activity):
    result = db.student_records.update_one(
        {"userIndex": userIndex},
        {"$pull": {"specialty": {"과목": subject, "활동": activity}}}
    )
    return result.modified_count

