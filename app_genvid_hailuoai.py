from flask import Flask, render_template, request, jsonify, send_file
import os
import time
import requests
import json
from datetime import datetime
import threading
import uuid
import google.generativeai as genai
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- API 설정 ---
api_key = "your_api_key" #hailuoai api key
group_id = "your_group_id" #hailuoai group id

# Gemini API 설정 (환경 변수에서 가져오거나 직접 설정)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'your_api_key')  # gemini api key
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 비디오 생성 매개변수
model = "MiniMax-Hailuo-02"
duration = 6
resolution = "1080P"

# 파일 업로드 설정
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 작업 상태를 저장할 딕셔너리
tasks = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def invoke_video_generation(prompt: str, mode: str = 'text', image_url: str = None) -> str:
    print("-----------------비디오 생성 작업 제출 중-----------------")
    url = "https://api.minimax.io/v1/video_generation"
    
    payload = {
        "model": model,
        "duration": duration,
        "resolution": resolution,
        "prompt_optimizer": True
    }
    
    if mode == 'text':
        payload["prompt"] = prompt
    elif mode == 'image':
        payload["prompt"] = prompt
        payload["image_url"] = image_url
    
    payload = json.dumps(payload)
    headers = {
        'authorization': 'Bearer ' + api_key,
        'content-type': 'application/json',
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()
        response_data = response.json()
        task_id = response_data.get('task_id')
        if task_id:
            print(f"비디오 생성 작업 성공적으로 제출됨, Task ID: {task_id}")
            return task_id
        else:
            print(f"API 응답에 'task_id'가 없습니다. 응답 내용: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"비디오 생성 작업 제출 실패: {e}")
        return None
    except Exception as e:
        print(f"응답 처리 중 예기치 않은 오류 발생: {e}")
        return None

def query_video_generation(task_id: str):
    url = f"https://api.minimax.io/v1/query/video_generation?task_id={task_id}"
    headers = {
        'authorization': 'Bearer ' + api_key
    }

    try:
        response = requests.request("GET", url, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        status = response_data.get('status')
        
        if status == 'Preparing':
            return "", 'Preparing'
        elif status == 'Queueing':
            return "", 'Queueing'
        elif status == 'Processing':
            return "", 'Processing'
        elif status == 'Success':
            file_id = response_data.get('file_id', '')
            return file_id, "Finished"
        elif status == 'Fail':
            return "", "Fail"
        else:
            return "", "Unknown"
    except requests.exceptions.RequestException as e:
        print(f"비디오 생성 상태 쿼리 실패: {e}")
        return "", "Error"
    except Exception as e:
        print(f"응답 처리 중 오류 발생: {e}")
        return "", "Error"

def fetch_video_result(file_id: str, task_uuid: str):
    print("---------------비디오 생성 성공, 다운로드 중---------------")
    url = f"https://api.minimax.io/v1/files/retrieve?GroupId={group_id}&file_id={file_id}"
    headers = {
        'authorization': 'Bearer ' + api_key,
        'content-type': 'application/json',
    }

    try:
        response = requests.request("GET", url, headers=headers)
        response.raise_for_status()
        response_data = response.json()

        download_url = response_data['file']['download_url']
        print("비디오 다운로드 링크：" + download_url)

        # output 폴더가 없으면 생성
        os.makedirs('output', exist_ok=True)
        
        # 타임스탬프 기반 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file_name = f"./output/minimax_video_{timestamp}.mp4"

        video_content = requests.get(download_url).content
        with open(output_file_name, 'wb') as f:
            f.write(video_content)
        
        # 작업 상태 업데이트
        tasks[task_uuid]['status'] = 'completed'
        tasks[task_uuid]['file_path'] = output_file_name
        print(f"비디오가 다음 경로에 다운로드되었습니다: {output_file_name}")
    except Exception as e:
        print(f"파일 다운로드 중 예기치 않은 오류 발생: {e}")
        tasks[task_uuid]['status'] = 'failed'

def chat_with_gemini(message: str) -> str:
    """Gemini와 채팅하여 프롬프트 추천을 받는 함수"""
    if not GEMINI_API_KEY:
        return "Gemini API 키가 설정되지 않았습니다. 환경 변수 GEMINI_API_KEY를 설정해주세요."
    
    try:
        # Gemini 모델 설정
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 프롬프트 추천을 위한 시스템 메시지
        system_prompt = """
        당신은 AI 비디오 생성 전문가입니다. 사용자가 원하는 비디오 장면을 설명하면, 
        MiniMax AI 비디오 생성 API에 최적화된 프롬프트를 추천해주세요.
        
        다음 사항을 고려해주세요:
        1. 구체적이고 상세한 장면 설명
        2. 카메라 움직임 ([Pan left], [Zoom in] 등)
        3. 시각적 효과 ([Slow motion], [Close up] 등)
        4. 분위기와 스타일
        5. 영어로 작성 (API 최적화)
        
        예시 형식:
        "In a luxurious restaurant, a person casually eats a fish-like creature with human arms and legs as a snack. Other elegantly dressed diners appear unfazed, calmly eating identical fish-monsters from their plates. [Pan right], [Zoom in]"
        """
        
        # 사용자 메시지와 시스템 프롬프트 결합
        full_prompt = f"{system_prompt}\n\n사용자 요청: {message}\n\n추천 프롬프트:"
        
        response = model.generate_content(full_prompt)
        return response.text.strip()
        
    except Exception as e:
        return f"Gemini API 호출 중 오류가 발생했습니다: {str(e)}"

def process_video_generation(prompt: str, task_uuid: str, mode: str = 'text', image_url: str = None):
    """비디오 생성을 백그라운드에서 처리하는 함수"""
    tasks[task_uuid]['status'] = 'submitting'
    
    task_id = invoke_video_generation(prompt, mode, image_url)
    if not task_id:
        tasks[task_uuid]['status'] = 'failed'
        return
    
    tasks[task_uuid]['status'] = 'processing'
    tasks[task_uuid]['task_id'] = task_id
    
    while True:
        time.sleep(10)
        file_id, status = query_video_generation(task_id)
        
        if file_id != "":
            fetch_video_result(file_id, task_uuid)
            break
        elif status == "Fail" or status == "Unknown" or status == "Error":
            tasks[task_uuid]['status'] = 'failed'
            break

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_video():
    data = request.get_json()
    prompt = data.get('prompt', '')
    mode = data.get('mode', 'text')
    image_url = data.get('image_url', '')
    
    if not prompt.strip():
        return jsonify({'error': '프롬프트를 입력해주세요.'}), 400
    
    if mode == 'image' and not image_url:
        return jsonify({'error': '이미지 URL을 입력해주세요.'}), 400
    
    # 고유한 작업 ID 생성
    task_uuid = str(uuid.uuid4())
    tasks[task_uuid] = {
        'status': 'starting',
        'prompt': prompt,
        'mode': mode,
        'image_url': image_url if mode == 'image' else None,
        'created_at': datetime.now().isoformat()
    }
    
    # 백그라운드에서 비디오 생성 시작
    thread = threading.Thread(target=process_video_generation, args=(prompt, task_uuid, mode, image_url))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_uuid,
        'message': '비디오 생성이 시작되었습니다.'
    })

@app.route('/upload_image', methods=['POST'])
def upload_image():
    """이미지 업로드 처리"""
    if 'image' not in request.files:
        return jsonify({'error': '이미지 파일이 없습니다.'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # 서버 URL 생성 (실제 배포 시에는 실제 도메인으로 변경 필요)
        image_url = f"http://localhost:5000/uploads/{filename}"
        
        return jsonify({
            'success': True,
            'image_url': image_url,
            'filename': filename
        })
    
    return jsonify({'error': '지원하지 않는 파일 형식입니다.'}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """업로드된 이미지 파일 제공"""
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/status/<task_id>')
def get_status(task_id):
    if task_id not in tasks:
        return jsonify({'error': '작업을 찾을 수 없습니다.'}), 404
    
    task = tasks[task_id]
    return jsonify({
        'status': task['status'],
        'prompt': task['prompt'],
        'created_at': task['created_at'],
        'file_path': task.get('file_path', '')
    })

@app.route('/chat', methods=['POST'])
def chat():
    """Gemini와 채팅하여 프롬프트 추천을 받는 엔드포인트"""
    data = request.get_json()
    message = data.get('message', '')
    
    if not message.strip():
        return jsonify({'error': '메시지를 입력해주세요.'}), 400
    
    response = chat_with_gemini(message)
    return jsonify({'response': response})

@app.route('/download/<task_id>')
def download_video(task_id):
    if task_id not in tasks:
        return jsonify({'error': '작업을 찾을 수 없습니다.'}), 404
    
    task = tasks[task_id]
    if task['status'] != 'completed':
        return jsonify({'error': '비디오가 아직 생성되지 않았습니다.'}), 400
    
    file_path = task.get('file_path', '')
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': '파일을 찾을 수 없습니다.'}), 404
    
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 