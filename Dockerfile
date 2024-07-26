# FROM ghcr.io/ggerganov/whisper.cpp:main-cuda
FROM ghcr.io/ggerganov/whisper.cpp:main

RUN apt-get -y update

RUN mkdir /models && ./models/download-ggml-model.sh tiny /models

RUN apt-get install -y python3-dev python3-pip pkg-config default-libmysqlclient-dev build-essential

RUN pip install --upgrade pip

WORKDIR /my-app

ADD requirements.txt /my-app

RUN pip install -r requirements.txt

ADD . /my-app

RUN chmod +x /my-app/entrypoint.sh

ENTRYPOINT ["/my-app/entrypoint.sh"]
