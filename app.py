from flask import Flask, request, jsonify
import json
import time
import threading
import requests
import uuid
import datetime
import os
import json
from dotenv import load_dotenv
app = Flask(__name__)
from flask_mysqldb import MySQL
from utils.create_db_and_tables import create_database_and_tables
from utils.version import API_VERSION, SERVICE_NAME
from utils.status_codes import StatusCodes
from uuid import uuid4
from api.models import WhisperRequestCall,WhisperRequestResult, response_template

import boto3
import subprocess
import tempfile
import json

# Load environment variables
load_dotenv()  # Take environment variables from.env.
app.config.from_object(__name__)  # Load config from object

# Load JSON configuration
with open('config.json') as f:
    config = json.load(f)

############### ENV VARIABLES ###############
SUPPORTED_METHOD = ["whisperit"]

############### ADD YOUR AI MARKETPLACE WEBHOOK ENDPOINT HERE ###############
webhook_url = "http://localhost:8000/callback"
# webhook_url = "https://marketplace-api-user.dev.devsaitech.com/api/v1/ai-connection/callback"


### Local cache : Need to make a database
cache = {}
cache_lock = threading.Lock()


############### ADD YOUR CUSTOM AI AGENT CALL HERE ###############
def download_file_from_s3(s3_path, local_dir):
    s3 = boto3.client('s3')
    bucket_name = s3_path.split('/')[2]
    file_key = '/'.join(s3_path.split('/')[3:])
    
    local_file_path = os.path.join(local_dir, os.path.basename(file_key))
    s3.download_file(bucket_name, file_key, local_file_path)
    # local_file_path = "/app/samples/jfk.mp3"
    return local_file_path

def upload_file_to_s3(local_file_path, s3_path):
    s3 = boto3.client('s3')
    bucket_name = s3_path.split('/')[2]
    file_key = '/'.join(s3_path.split('/')[3:])

    s3.upload_file(local_file_path, bucket_name, file_key)

def process_audio_file(s3_path):
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Download the file from S3
        local_file_path = download_file_from_s3(s3_path, tmpdirname)
        wav_file_path = os.path.join(tmpdirname, 'audio.wav')
        
        # Convert to wav using ffmpeg
        ffmpeg_command = f'ffmpeg -i {local_file_path} -f wav -ar 16000 {wav_file_path}'
        subprocess.run(ffmpeg_command, shell=True, check=True)
        
        # Run the main command with the correct arguments
        main_command = f'/app/main -m /models/ggml-tiny.bin -f {wav_file_path} -dtw tiny -ojf'
        subprocess.run(main_command, shell=True, check=True)
        
        main_command1 = f'/app/main -m /models/ggml-tiny.bin -f {wav_file_path} -owts -fp /my-app/Courier_New_Bold.ttf'
        subprocess.run(main_command1, shell=True, check=True)
        main_command2 = f'source -f {wav_file_path}.wts'
        subprocess.run(main_command2, shell=True, check=True)
        

        # Read the resulting JSON file
        json_file_path = f'{wav_file_path}.json'
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)
        
        # Video file created
        video_file_path = f'{wav_file_path}.mp4'
        
        # Extract the required information
        result = data.get('result')
        transcription = data.get('transcription')
        combined_json = {'result': result, 'transcription': transcription}
        
        # Clean up temporary files
        os.remove(local_file_path)
        os.remove(wav_file_path)
        os.remove(json_file_path)
        
        return combined_json, video_file_path

def hello_world(payload):
    start_time = time.time()
    time.sleep(5)  # Placeholder for actual task processing
    data_s3 = payload['data_s3']
    text,video_file_path = process_audio_file(data_s3)    
    end_time = time.time()
    processing_duration = end_time - start_time  # Calculate processing duration in seconds
    return text, video_file_path, processing_duration
    



############### CHECK IF ALL INFORMATION IS IN REQUEST ###############
def check_input_request(request):
    reason = ""
    status = ""
    user_id = request.headers.get('X-User-ID', None)
    user_role = request.headers.get('X-User-Role', None)
    
    if user_role is None or not user_role.strip():
        status = StatusCodes.INVALID_REQUEST
        reason = "userRole is invalid"

    if user_id is None or not user_id.strip():
        status = StatusCodes.INVALID_REQUEST
        reason = "userToken is invalid"
    
    request_id = request.headers.get('x-request-id', None)
    request_data = request.get_json()
    print(request_data)
    respose_data = None

    method = request_data['method']
    print(method)
    if request_id is None or not request_id.strip():
        status = StatusCodes.INVALID_REQUEST
        reason = "requestId is invalid"
    if method is None or not method.strip():
        status = StatusCodes.INVALID_REQUEST
        reason = "method is invalid"
    elif method not in SUPPORTED_METHOD:
        status = StatusCodes.UNSUPPORTED
        reason = f"unsupported method {method}"
    
    payload = request_data['payload']
    if payload is None:
        status = StatusCodes.INVALID_REQUEST
        reason = "payload is invalid"
    if payload == "":
        status = StatusCodes.INVALID_REQUEST
        reason = "payload is invalid"
    if payload['data_s3'] == "":
        status = StatusCodes.INVALID_REQUEST
        reason = "data_s3 is invalid"
    
    if status != "":
        trace_id = uuid4().hex
        error_code = {
            "status": status,
            "reason": reason
        }
        respose_data = response_template(request_id, trace_id, -1,True, {}, error_code)
    
    return respose_data

############### API ENDPOINT TO RECEIVE REQUEST ###############
@app.route('/call', methods=['POST'])
def call_endpoint():
    user_id = request.headers.get('X-User-ID', None)
    
    ret = check_input_request(request)
    if ret is not None:
        return ret

    task_id = str(uuid.uuid4())
    requestId = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    # Response preparation
    response = {"taskId": task_id}
    error_code = {"status": StatusCodes.PENDING, "reason": "Pending"}
    respose_data = response_template(requestId, trace_id, -1, False, response, error_code)

    # Payload data
    request_data = request.get_json()
    payload = request_data['payload']

    # Task processing in a separate thread
    threading.Thread(target=process_task, args=(task_id,requestId,user_id,payload,)).start()

    # Immediate response to the client
    return jsonify(respose_data), 200


############### PROCESS THE CALL TASK HERE ###############
def success_response(task_id, data, dataType, requestId, trace_id, process_duration):
        # Prepare the response
        response = {
            "taskId": task_id,  # Assuming task_id is defined somewhere
            "data": data,
            "dataType": dataType
        }
        error_code = {"status": StatusCodes.SUCCESS, "reason": "success"}
        response_data = response_template(requestId, trace_id, process_duration, True, response, error_code)
        return response_data



def process_task(task_id,requestId, user_id, payload):
    data, video_file_path, processing_duration = hello_world(payload)
    # S3 upload the video file
    upload_file_to_s3(video_file_path, payload['data_s3'].replace('.mp3', '_result.mp3'))

    # Save in local cache : Need to make a database
    with cache_lock:
        cache[task_id] = { data, video_file_path, processing_duration }

    # Send the callback
    send_callback(user_id, task_id,requestId,processing_duration, data, payload['data_s3'].replace('.mp3', '_result.mp3'))

            
############### SEND CALLBACK TO YOUR APP MARKETPLACE ENDPOINT WITH TASK RESPONSE ###############
def send_callback(user_id, task_id,requestId, processing_duration, data, s3_path):
    
    callback_message = {
        "apiVersion": API_VERSION,
        "service": SERVICE_NAME,
        "datetime": datetime.datetime.now().isoformat(),
        "processDuration": processing_duration,  # Simulated duration
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
        "x-request-id": requestId,
        "x-user-id": user_id,
        "x-user-role": "publisher"
    }

    response = requests.post(webhook_url, json=callback_message, headers=headers)





############### WHEN THIS API ENDPOINT IS PINGED WITH A TASKID IT RETURNS THE TASK STATUS AND DATA ###############

###### USE YOUR OWN DATABASE TO STORE TASKID : RESULT ######
@app.route('/result', methods=['POST'])
def result():
    user_id = request.headers.get('X-User-ID', None)
    requestId = request.headers.get('x-request-id', None)
    request_data = request.get_json()
    taskID = request_data.get("taskId")
    trace_id = str(uuid.uuid4())
    result_request_id = str(uuid.uuid4())
    if user_id is None or not user_id.strip():
        error_code = {"status": StatusCodes.ERROR, "reason": "No User ID found in headers"}
        response_data = response_template(result_request_id, trace_id, -1, True, {}, error_code)
        return response_data

    if requestId is None or not requestId.strip():
        error_code = {"status": StatusCodes.ERROR, "reason": "No request ID found in headers"}
        response_data = response_template(result_request_id, trace_id, -1, True, {}, error_code)
        return response_data
    
    if taskID is None or not taskID.strip():
        error_code = {"status": StatusCodes.ERROR, "reason": "No task ID found in body"}
        response_data = response_template(result_request_id, trace_id, -1, True, {}, error_code)
        return response_data

    print(taskID)
    if taskID not in cache:
        error_code = {"status": StatusCodes.ERROR, "reason": "Task ID not exists in db"}
        response_data = response_template(result_request_id, trace_id, -1, True, {}, error_code)
        return response_data
    
    data = {
        "dataType": 'HYBRID',
        "data": cache[taskID][0],
        "s3Path": cache[taskID][1]
    }
    response_data = success_response(
        taskID, data, requestId, trace_id, -1
    )
    # print(data)
    return jsonify(response_data), 200






############### RUN YOUR SERVER HERE ###############
if __name__ == '__main__':
    app.run(debug=True)
