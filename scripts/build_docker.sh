#!/bin/bash
ECR="xxxx/whisperer"
TAG=$(jq -r '.api_version' version.json)
SERVICE="my-ai-app"
IMAGE_NAME="${ECR}:${SERVICE}_${TAG}"
sudo docker build -t $IMAGE_NAME  .
echo  image $IMAGE_NAME is built