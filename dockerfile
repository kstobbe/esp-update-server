# syntax=docker/dockerfile:1
FROM python:3.8-slim-buster
COPY . /esp-update-server
WORKDIR /esp-update-server

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
ENV FLASK_APP=server
ENV FLASK_ENV=development
EXPOSE 5000
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]