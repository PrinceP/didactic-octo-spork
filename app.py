from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
import time
import threading
import requests
import uuid
import datetime
import os
import json
from dotenv import load_dotenv
import boto3
import subprocess
import tempfile

# Load environment variables
load_dotenv()

app = FastAPI()

# Load JSON configuration
with open('config.json') as f:
    config = json.load(f)

SUPPORTED_METHOD = ["whisperit"]

# Local cache: Need to make a database
cache = {}
cache_lock = threading.Lock()

webhook_url = "http://localhost:8002/callback"

class Payload(BaseModel):
    data_s3: str

class RequestData(BaseModel):
    method: str
    payload: Payload

class ResultRequest(BaseModel):
    taskId: str

def download_file_from_s3(s3_path, local_dir):
    s3 = boto3.client('s3')
    bucket_name = s3_path.split('/')[2]
    file_key = '/'.join(s3_path.split('/')[3:])

    local_file_path = os.path.join(local_dir, os.path.basename(file_key))
    s3.download_file(bucket_name, file_key, local_file_path)
    return local_file_path

def upload_file_to_s3(local_file_path, s3_path):
    s3 = boto3.client('s3')
    bucket_name = s3_path.split('/')[2]
    file_key = '/'.join(s3_path.split('/')[3:])

    s3.upload_file(local_file_path, bucket_name, file_key)

def process_audio_file(s3_path):
    with tempfile.TemporaryDirectory() as tmpdirname:
        local_file_path = download_file_from_s3(s3_path, tmpdirname)
        wav_file_path = os.path.join(tmpdirname, 'audio.wav')

        ffmpeg_command = f'ffmpeg -i {local_file_path} -f wav -ar 16000 {wav_file_path}'
        subprocess.run(ffmpeg_command, shell=True, check=True)

        main_command = f'/app/main -m /models/ggml-tiny.bin -f {wav_file_path} -dtw tiny -ojf'
        subprocess.run(main_command, shell=True, check=True)

        main_command1 = f'/app/main -m /models/ggml-tiny.bin -f {wav_file_path} -owts -fp /my-app/Courier_New_Bold.ttf'
        subprocess.run(main_command1, shell=True, check=True)
        main_command2 = f'source -f {wav_file_path}.wts'
        subprocess.run(main_command2, shell=True, check=True)

        json_file_path = f'{wav_file_path}.json'
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)

        video_file_path = f'{wav_file_path}.mp4'
        result = data.get('result')
        transcription = data.get('transcription')
        combined_json = {'result': result, 'transcription': transcription}

        os.remove(local_file_path)
        os.remove(wav_file_path)
        os.remove(json_file_path)

        return combined_json, video_file_path

def hello_world(payload):
    start_time = time.time()
    time.sleep(5)
    data_s3 = payload.data_s3
    text, video_file_path = process_audio_file(data_s3)
    end_time = time.time()
    processing_duration = end_time - start_time
    return text, video_file_path, processing_duration

def check_input_request(request, user_id, user_role, request_id, method, payload):
    reason = ""
    status = ""
    if user_role is None or not user_role.strip():
        status = "INVALID_REQUEST"
        reason = "userRole is invalid"

    if user_id is None or not user_id.strip():
        status = "INVALID_REQUEST"
        reason = "userToken is invalid"

    if request_id is None or not request_id.strip():
        status = "INVALID_REQUEST"
        reason = "requestId is invalid"
    if method is None or not method.strip():
        status = "INVALID_REQUEST"
        reason = "method is invalid"
    elif method not in SUPPORTED_METHOD:
        status = "UNSUPPORTED"
        reason = f"unsupported method {method}"

    if payload is None or payload == "" or payload.data_s3 == "":
        status = "INVALID_REQUEST"
        reason = "payload is invalid"

    if status != "":
        trace_id = uuid.uuid4().hex
        error_code = {
            "status": status,
            "reason": reason
        }
        respose_data = {
            "requestId": request_id,
            "traceId": trace_id,
            "processingDuration": -1,
            "isResponseImmediate": True,
            "response": {},
            "errorCode": error_code
        }
        return respose_data
    return None

@app.post("/call")
async def call_endpoint(request: Request, user_id: str = Header(None), user_role: str = Header(None), request_id: str = Header(None), marketplace-token: str = Header(None), request_data: RequestData = None):
    ret = check_input_request(request, user_id, user_role, request_id, request_data.method, request_data.payload)
    if ret is not None:
        raise HTTPException(status_code=400, detail=ret)

    task_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    response = {"taskId": task_id}
    error_code = {"status": "PENDING", "reason": "Pending"}
    respose_data = {
        "requestId": request_id,
        "traceId": trace_id,
        "processingDuration": -1,
        "isResponseImmediate": False,
        "response": response,
        "errorCode": error_code
    }

    threading.Thread(target=process_task, args=(task_id, request_id, user_id, request_data.payload,)).start()

    return JSONResponse(content=respose_data)

def process_task(task_id, request_id, user_id, payload):
    data, video_file_path, processing_duration = hello_world(payload)
    upload_file_to_s3(video_file_path, payload.data_s3.replace('.mp3', '_result.mp3'))

    with cache_lock:
        cache[task_id] = (data, video_file_path, processing_duration)

    send_callback(user_id, task_id, request_id, processing_duration, data, payload.data_s3.replace('.mp3', '_result.mp3'))

def send_callback(user_id, task_id, request_id, processing_duration, data, s3_path):
    callback_message = {
        "apiVersion": "1.0.0",
        "service": "MyService",
        "datetime": datetime.datetime.now().isoformat(),
        "processDuration": processing_duration,
        "taskId": task_id,
        "isResponseImmediate": False,
        "response": {
            "dataType": "HYBRID",
            "data": data,
            "s3Path": s3_path
        },
        "errorCode": {
            "status": "WSP_000",
            "reason": "success"
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-marketplace-token": "1df239ef34d92aa8190b8086e89196ce41ce364190262ba71964e9f84112bc45",
        "x-request-id": request_id,
        "x-user-id": user_id,
        "x-user-role": "publisher"
    }

    response = requests.post(webhook_url, json=callback_message, headers=headers)

@app.post("/result")
async def result(request: Request, user_id: str = Header(None), user_role: str = Header(None), marketplace_token: str = Header(None), request_data: ResultRequest = None):
    trace_id = str(uuid.uuid4())
    result_request_id = str(uuid.uuid4())

    if user_id is None or not user_id.strip():
        error_code = {"status": "ERROR", "reason": "No User ID found in headers"}
        response_data = {
            "requestId": result_request_id,
            "traceId": trace_id,
            "processingDuration": -1,
            "isResponseImmediate": True,
            "response": {},
            "errorCode": error_code
        }
        raise HTTPException(status_code=400, detail=response_data)

    if marketplace_token is None or not marketplace_token.strip():
        error_code = {"status": "ERROR", "reason": "No marketplace token found in headers"}
        response_data = {
            "requestId": result_request_id,
            "traceId": trace_id,
            "processingDuration": -1,
            "isResponseImmediate": True,
            "response": {},
            "errorCode": error_code
        }
        raise HTTPException(status_code=400, detail=response_data)

    task_id = request_data.taskId
    if task_id is None or not task_id.strip():
        error_code = {"status": "ERROR", "reason": "No task ID found in body"}
        response_data = {
            "requestId": result_request_id,
            "traceId": trace_id,
            "processingDuration": -1,
            "isResponseImmediate": True,
            "response": {},
            "errorCode": error_code
        }
        raise HTTPException(status_code=400, detail=response_data)

    if task_id not in cache:
        error_code = {"status": "ERROR", "reason": "Task ID not exists in db"}
        response_data = {
            "requestId": result_request_id,
            "traceId": trace_id,
            "processingDuration": -1,
            "isResponseImmediate": True,
            "response": {},
            "errorCode": error_code
        }
        raise HTTPException(status_code=400, detail=response_data)

    data = {
        "dataType": 'HYBRID',
        "data": cache[task_id][0],
        "s3Path": cache[task_id][1]
    }
    response_data = {
        "requestId": request_id,
        "traceId": trace_id,
        "processingDuration": -1,
        "isResponseImmediate": True,
        "response": {
            "taskId": task_id,
            "data": data,
            "dataType": "HYBRID"
        },
        "errorCode": {"status": "SUCCESS", "reason": "success"}
    }
    return JSONResponse(content=response_data)


