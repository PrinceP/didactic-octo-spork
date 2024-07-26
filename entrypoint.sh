#!/bin/bash

# Start the main application with uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000 &

# Start the local webhook receiver
python3 local_webhook_receiver.py &

# Wait for all background processes to finish
wait

