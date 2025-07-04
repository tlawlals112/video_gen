import os
import time
import requests
import json
from datetime import datetime

# --- API 설정 ---
api_key = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLsi6zsp4Drr7wiLCJVc2VyTmFtZSI6IuyLrOyngOuvvCIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxOTM5OTQ1MDYzMzUwMDE0NDI1IiwiUGhvbmUiOiIiLCJHcm91cElEIjoiMTkzOTk0NTA2MzM0NTgyMDEyMSIsIlBhZ2VOYW1lIjoiIiwiTWFpbCI6InRsYXdsYWxzMTEyQGdtYWlsLmNvbSIsIkNyZWF0ZVRpbWUiOiIyMDI1LTA3LTAxIDE2OjUzOjM0IiwiVG9rZW5UeXBlIjoxLCJpc3MiOiJtaW5pbWF4In0.Ao7w4-mUThTPp_NphSgyHfvRTaPuIA7yBKRQICQ83PEuShz8TrU-bK8jbBmj45aA9tzam_ocovXatsRctVPgWQSNUP2xsEwdvVFioOfqqhcXEG5zKq1KZhHtsjiZhKaoNr9N97aAkjiAM_uwUhtKfMpp8PBID9YcpYI9gY84r85XkxX4Ke-tp5qo2RiLjiy6JYwOtGHa5y0pa-gEHIRnSTLDeUOr1wKf913gLvLGXTY9p15uUohYnN2CK3F4Lf6_Je5iToNg1wuk0NT1PI0v6YQNNeD3k_DNVhpxJ3eO9xIC5BmK_7pGaae3qnDCP7IyIIQjoKtRIf5Ge_AIrYRZkw"
group_id = "1939945063345820121" # API 키에서 추출된 group_id로 보입니다.

# --- 비디오 생성 매개변수 ---
# 오류 메시지에 따라 MiniMax-Hailuo-02 모델과 1080P 해상도로 변경합니다.
model = "MiniMax-Hailuo-02"
# prompt_optimizer는 기본값이 True이므로 텍스트-비디오 모델에서 프롬프트 최적화에 도움이 됩니다.
prompt = (
    "In an opulent, high-class restaurant, a person is casually devouring a fish-like creature "
    "with human arms and legs as a snack, its flesh casually torn. Other elegantly dressed "
    "diners around them appear completely unfazed, calmly eating identical fish-monsters "
    "from their own plates. Meanwhile, an identical, vacant-eyed fish-monster is giving the "
    "person a piggyback ride, standing silently amidst the refined ambiance. [Pan right], [Zoom in]"
)

duration = 6 # MiniMax-Hailuo-02 모델 1080P는 6초를 지원합니다.
resolution = "1080P" # 오류 메시지에 따라 1080P로 변경

# --- 타임스탬프 기반 파일명 생성 ---
base_output_filename = "minimax_video.mp4"
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
name, ext = os.path.splitext(base_output_filename)
output_file_name = f"./output/{name}_{timestamp}{ext}"
print(f"생성된 비디오는 '{output_file_name}' 이름으로 저장됩니다.")
# ----------------------------------------------------------------------


def invoke_video_generation() -> str:
    print("-----------------비디오 생성 작업 제출 중-----------------")
    url = "https://api.minimax.io/v1/video_generation"
    payload = json.dumps({
        "prompt": prompt,
        "model": model,
        "duration": duration,
        "resolution": resolution,
        "prompt_optimizer": True
    })
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
        print(f"응답 내용: {response.text}")
        return None
    except Exception as e:
        print(f"응답 처리 중 예기치 않은 오류 발생: {e}. 응답 내용: {response.text}")
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
            print("...준비 중...")
            return "", 'Preparing'
        elif status == 'Queueing':
            print("...대기열에 있음...")
            return "", 'Queueing'
        elif status == 'Processing':
            print("...생성 중...")
            return "", 'Processing'
        elif status == 'Success':
            file_id = response_data.get('file_id', '')
            print(f"비디오 생성 완료! File ID: {file_id}")
            return file_id, "Finished"
        elif status == 'Fail':
            print(f"비디오 생성 실패. 응답: {response.text}")
            return "", "Fail"
        else:
            print(f"알 수 없는 상태: {status}. 응답: {response.text}")
            return "", "Unknown"
    except requests.exceptions.RequestException as e:
        print(f"비디오 생성 상태 쿼리 실패: {e}")
        return "", "Error"
    except Exception as e:
        print(f"응답 처리 중 오류 발생: {e}. 응답 내용: {response.text}")
        return "", "Error"


def fetch_video_result(file_id: str):
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

        video_content = requests.get(download_url).content
        with open(output_file_name, 'wb') as f:
            f.write(video_content)
        print(f"비디오가 다음 경로에 다운로드되었습니다: {os.path.join(os.getcwd(), output_file_name)}")
    except requests.exceptions.RequestException as e:
        print(f"비디오 결과 다운로드 실패: {e}")
        print(f"응답 내용: {response.text}")
    except KeyError:
        print(f"'download_url' 또는 'file' 키를 응답에서 찾을 수 없습니다. 응답 내용: {response.text}")
    except Exception as e:
        print(f"파일 다운로드 중 예기치 않은 오류 발생: {e}")


if __name__ == '__main__':
    # API Key와 Group ID가 올바르게 설정되었는지 확인
    if not api_key:
        print("오류: 'api_key'를 실제 값으로 채워주세요.")
    elif not group_id:
        print("오류: 'group_id'를 실제 값으로 채워주세요.")
    else:
        task_id = invoke_video_generation()
        if task_id:
            print("-----------------비디오 생성 작업 제출 완료-----------------")
            while True:
                time.sleep(10)

                file_id, status = query_video_generation(task_id)
                if file_id != "":
                    fetch_video_result(file_id)
                    print("---------------작업 성공---------------")
                    break
                elif status == "Fail" or status == "Unknown" or status == "Error":
                    print("---------------작업 실패---------------")
                    break
