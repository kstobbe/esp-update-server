# syntax=docker/dockerfile:1
FROM python:3.10.1
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY ./server /server
ENV FLASK_APP=server
ENV FLASK_ENV=production
EXPOSE 5000
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]