# Whisper Text AI

## Nginx for AWS[Optional]

To enable other source to access our ubuntu instance, we need to configure Nginx.

```sh
sudo apt install nginx
```

By default, Nginx contains one server block called default. You can find it in this location: etc/nginx/sites-enabled.

Now at your root, run
```sh
cd /etc/nginx/sites-enabled/
sudo vim fastapi_nginx
```
>> Note: You should change server_name to your instance Public IPv4 address.

```json
server {
    listen 80;
    server_name 13.60.40.19;
    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Start Nginx server:
```sh
sudo service nginx restart
```

## Docker build

```sh
./scripts/build_docker.sh
```

## Deployment
```sh
sudo docker run -d -p 8000:8000 xxxx/whisperer:my-ai-app_1.0.1
```

## Sample payload for /call
```json
{
  "method": "whisperit",
  "payload": {
    "data_s3": "s3://for-whisper-files/jfk.mp3"
}
```
