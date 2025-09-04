from flask import Flask, render_template, make_response, jsonify, request, redirect, url_for
import DBMgr, OpenAIHelper, json
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, set_access_cookies, set_refresh_cookies
)
from datetime import timedelta

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = "hashingKey"
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_SECURE"] = False
app.config["JWT_COOKIE_SAMESITE"] = "Lax"
app.config["JWT_COOKIE_CSRF_PROTECT"] = True
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=5)

jwt = JWTManager(app)

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return redirect(url_for('home'))

@app.route('/')
@jwt_required(optional=True)
def home():
    user_id = get_jwt_identity()
    if user_id:
        return redirect(url_for('mypage'))
    return render_template('login.html')

@app.route('/index')
def ee():
    return render_template('index.html')

@app.route('/feedback')
def feedback_page():
    return render_template('feedback.html')

@app.route('/make')
@jwt_required() # Protect this page as it involves AI generation
def make_page():
    return render_template('make.html')

@app.route('/ANALYZE_STUDENT_RECORD', methods=['GET'])
def AnalyzeStudentRecord():
    userIndex = request.args.get('userIndex', type=int)
    university_name = request.args.get('university')
    department = request.args.get('department')
    
    if userIndex is None or not university_name or not department:
        return jsonify({"error":"userIndex, university, department 필요"}),400

    user_data = DBMgr.db.user.find_one({"userIndex":userIndex})
    if not user_data:
        return jsonify({"error":"유효하지 않은 사용자 인덱스"}),400

    record = DBMgr.GetStudentRecord(userIndex)
    if not record or not record.get('main'): # Check if record exists and has 'main' data
        return jsonify({"error":"생활기록부 없음"}),400

    univ_info = DBMgr.GetUniversityInfo(university_name)
    if not univ_info:
        return jsonify({"error":"대학 정보 없음"}),400

    if '_id' in record:
        del record['_id']
    student_text = json.dumps(record, ensure_ascii=False)
    rates = OpenAIHelper.predict_acceptance_rate(student_text, univ_info.get("tier","A"), department)
    final_result = OpenAIHelper.calculate_final_rate(rates, univ_info)

    # 1. user 컬렉션 업데이트
    DBMgr.db.user.update_one(
        {"userIndex":userIndex},
        {"$set":{
            "studentRecord.지원 대학 이름": university_name,
            "studentRecord.지원 학과": department,
            "studentRecord.합격률": final_result['final_rate'],
            "studentRecord.합격률 등급": final_result['category']
        }}
    )

    # 2. result 컬렉션에 저장
    DBMgr.db.result.insert_one({
        "userIndex": userIndex,
        "university": university_name,
        "department": department,
        "acceptRate": float(final_result['final_rate']),  # 실수형으로 저장
        "acceptGrade": final_result['category']
    })

    return render_template("result.html",
        university=university_name,
        category=final_result['category'],
        final_rate=final_result['final_rate']
    )

@app.route("/GET_USER_RESULTS", methods=["GET"])
@jwt_required()  # 로그인 필수
def get_user_results():
    user_id = get_jwt_identity()
    user_data = DBMgr.GetUserById(user_id)
    if not user_data:
        return jsonify({"success": False, "results": []})

    results = list(DBMgr.db.result.find({"userIndex": user_data['userIndex']}, {"_id":0}))
    for r in results:
        r['acceptRate'] = int(r.get('acceptRate', 0))
    return render_template("record.html", results=results)

@app.route('/CHECK_STUDENT_RECORD', methods=['GET'])
def CheckStudentRecord():
    userIndex = request.args.get('userIndex', type=int)
    exists = DBMgr.HasStudentRecord(userIndex) if userIndex is not None else False
    return jsonify({'exists': exists})

@app.route('/JOIN', methods=['POST'])
def JoinUser():
    raw_pw = request.form['pw']
    hashed_pw = generate_password_hash(raw_pw)
    userIndex = DBMgr.InsertUser(request.form['id'], hashed_pw)
    return jsonify({'result':"success" if userIndex is not None else "failure", 'userIndex': userIndex})

@app.route("/LOGOUT", methods=["POST"])
def logout():
    resp = make_response(jsonify({"result":"success"}))
    resp.delete_cookie("access_token_cookie")
    resp.delete_cookie("refresh_token_cookie")
    return resp

@app.route('/LOGIN', methods=['POST'])
def LoginUser():
    user = DBMgr.GetUserById(request.form['id'])
    if user is None or not check_password_hash(user['pw'], request.form['pw']):
        return jsonify({'result':'failure','userIndex':None}),401

    access_token = create_access_token(identity=user['id'], additional_claims={"type":"access"})
    refresh_token = create_refresh_token(identity=user['id'], additional_claims={"type":"refresh"})
    resp = make_response(jsonify({'result':'success','userIndex':user['userIndex']}))
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp

@app.route("/REFRESH", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    id = get_jwt_identity()
    resp = make_response(jsonify({"result":"success"}))
    set_access_cookies(resp, create_access_token(identity=id, additional_claims={"type":"access"}))
    return resp

@app.route('/CHECKID', methods=['GET'])
def CheckId():
    hasId = DBMgr.HasId(request.args.get('id'))
    return jsonify({'result': 'failure' if hasId else 'success'})

@app.route("/DELETE_RESULT", methods=["POST"])
def delete_result():
    data = request.get_json()
    userIndex = data.get("userIndex")
    university = data.get("university")
    department = data.get("department")

    if userIndex is None or not university or not department:
        return jsonify({"success": False, "message": "필수 데이터 누락"})

    # DB에서 해당 결과 삭제
    result = DBMgr.db.result.delete_one({
        "userIndex": userIndex,
        "university": university,
        "department": department
    })

    if result.deleted_count > 0:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "삭제할 데이터가 없음"})

@app.route('/SAVE_RESULT', methods=['POST'])
@jwt_required()  # 로그인 필수
def save_result():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '데이터 없음'}), 400
    
    # JWT에서 user id 가져오기
    user_id = get_jwt_identity()
    user_data = DBMgr.GetUserById(user_id)
    if not user_data:
        return jsonify({'success': False, 'message': '사용자 정보 없음'}), 400
    
    university = data.get('university')
    accept_rate = data.get('acceptRate')
    accept_grade = data.get('acceptGrade')

    try:
        DBMgr.db.result.insert_one({
            "userIndex": user_data['userIndex'],
            "university": university,
            "department": "",  
            "acceptRate": float(accept_rate),
            "acceptGrade": accept_grade
        })
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/SELECTUNIV')
def SelectUniv():
    univ_names = [u['name'] for u in DBMgr.GetAllUniversities()]
    return render_template('selectUniv.html', universities=univ_names)

# --- Merged MyPage Routes ---

def _get_user_record():
    user_id = get_jwt_identity()
    user_data = DBMgr.GetUserById(user_id)
    if not user_data:
        return None, None
    user_index = user_data['userIndex']
    record = DBMgr.GetStudentRecord(user_index)
    return user_index, record if record else {}

@app.route('/mypage')
@jwt_required()
def mypage():
    user_index, user_record = _get_user_record()
    if user_index is None:
        return jsonify({'result': 'failure', 'message': 'User not found'}), 401
    
    # Ensure main data structure exists for all grades
    main_data = user_record.get('main', {})
    for grade in ['1', '2', '3']:
        if grade not in main_data:
            main_data[grade] = {'career_aspiration': '', 'average_grade': ''}

    return render_template("mypage_main.html", user_main_data=main_data)

@app.route('/mypage/specialty')
@jwt_required()
def mypage_specialty():
    user_index, user_record = _get_user_record()
    if user_index is None:
        return jsonify({'result': 'failure', 'message': 'User not found'}), 401
    return render_template("mypage_specialty.html", user=user_record)

@app.route('/mypage/activities')
@jwt_required()
def mypage_activities():
    user_index, user_record = _get_user_record()
    if user_index is None:
        return jsonify({'result': 'failure', 'message': 'User not found'}), 401

    # Pass the entire user_record to the template
    # The template will handle accessing user.activities directly
    return render_template("mypage_activities.html", user=user_record)

@app.route('/mypage/save', methods=['POST'])
@jwt_required()
def mypage_save():
    try:
        user_index, user_record = _get_user_record()
        if user_index is None:
            return jsonify({'result': 'failure', 'message': 'User not found'}), 401

        payload = request.get_json()
        print(f"Received payload for user {user_index}: {payload}") # DEBUGGING

        if not payload:
            return jsonify({'result': 'failure', 'message': 'No data provided'}), 400

        update_key = None
        update_data = None

        if 'main' in payload:
            grade_data = payload['main']
            grade = grade_data.get('grade')
            if grade in ['1', '2', '3']:
                update_key = f"main.{grade}"
                update_data = {
                    'career_aspiration': grade_data.get('career_aspiration'),
                    'average_grade': grade_data.get('average_grade')
                }
        elif 'activities' in payload:
            update_key = "activities"
            update_data = payload['activities']
        elif 'specialty' in payload:
            update_key = "specialty"
            update_data = payload['specialty']

        if update_key and update_data is not None:
            DBMgr.UpdateStudentRecord(user_index, update_key, update_data)
            return jsonify({'result': 'success'})
        else:
            print(f"Failed to determine update_key or update_data for payload: {payload}") # DEBUGGING
            return jsonify({'result': 'failure', 'message': f'Invalid data: update_key={update_key}, update_data={update_data}'}), 400

    except Exception as e:
        print(f"An error occurred in /mypage/save: {e}") # DEBUGGING
        return jsonify({'result': 'failure', 'message': 'An internal error occurred'}), 500

@app.route('/mypage/delete_specialty', methods=['POST'])
@jwt_required()
def delete_specialty():
    try:
        user_id = get_jwt_identity()
        user_data = DBMgr.GetUserById(user_id)
        if not user_data:
            return jsonify({'success': False, 'message': 'User not found'}), 401

        user_index = user_data['userIndex']
        data = request.get_json()
        subject = data.get('subject')
        activity = data.get('activity')

        if not subject or not activity:
            return jsonify({'success': False, 'message': 'Subject and activity are required'}), 400

        # Call DBMgr to delete the specialty item
        deleted_count = DBMgr.DeleteSpecialtyItem(user_index, subject, activity)

        if deleted_count > 0:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Item not found or not deleted'}), 404

    except Exception as e:
        print(f"An error occurred in /mypage/delete_specialty: {e}") # DEBUGGING
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/generate_feedback', methods=['POST'])
@jwt_required()
def generate_feedback_api():
    try:
        user_id = get_jwt_identity() # Ensure user is logged in
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        data = request.get_json()
        student_text = data.get('student_text')

        if not student_text:
            return jsonify({'success': False, 'message': '생활기록부 내용이 필요합니다.'}), 400

        feedback = OpenAIHelper.generate_feedback(student_text)
        return jsonify({'success': True, 'feedback': feedback})

    except Exception as e:
        print(f"An error occurred in /generate_feedback: {e}") # DEBUGGING
        return jsonify({'success': False, 'message': '피드백 생성 중 오류가 발생했습니다.'}), 500

@app.route('/generate_special_record', methods=['POST'])
@jwt_required()
def generate_special_record_api():
    try:
        user_id = get_jwt_identity() # Ensure user is logged in
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        data = request.get_json()
        user_index = data.get('userIndex') # Get userIndex
        style_tone_text = data.get('style_tone_text') # Get style/tone text

        if user_index is None:
            return jsonify({'success': False, 'message': '사용자 인덱스가 필요합니다.'}), 400
        
        # Fetch student record from DB
        user_data = DBMgr.GetUserById(user_id) # Get user data to find userIndex
        if not user_data or user_data['userIndex'] != user_index:
            return jsonify({'success': False, 'message': '사용자 정보를 찾을 수 없습니다.'}), 400

        student_record_data = DBMgr.GetStudentRecord(user_index)
        if not student_record_data:
            return jsonify({'success': False, 'message': '생활기록부 데이터가 없습니다.'}), 400

        # Remove ObjectId to make it JSON serializable
        if '_id' in student_record_data:
            del student_record_data['_id']

        # Pass both student_record_data and style_tone_text to OpenAIHelper
        generated_record = OpenAIHelper.generate_special_record(student_record_data, style_tone_text)
        return jsonify({'success': True, 'generated_record': generated_record})

    except Exception as e:
        print(f"An error occurred in /generate_special_record: {e}") # DEBUGGING
        return jsonify({'success': False, 'message': '생기부 생성 중 오류가 발생했습니다.'}), 500

# --------------------------

if __name__=='__main__':
    DBMgr.Initialize()
    DBMgr.InsertTestStudentRecord()
    app.run('0.0.0.0', port=5000, debug=True)
