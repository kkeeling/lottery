FROM python:3.7-buster

RUN apt-get update --fix-missing && apt-get install -y \
    libjpeg62-turbo-dev \
    libpng-dev \
    gdal-bin

RUN apt-get clean


COPY ./requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
RUN date
WORKDIR /opt/lottery