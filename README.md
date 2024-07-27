# Whisper Text AI

## Docker build

```sh
./scripts/build_docker.sh
```

## Deployment
sudo docker run -d -p 8000:8000 xxxx/whisperer:my-ai-app_1.0.1

## Sample payload for /call
```json
{
  "method": "whisperit",
  "payload": {
    "data_s3": "s3://for-whisper-files/jfk.mp3"
}
```
