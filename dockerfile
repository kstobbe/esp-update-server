FROM python:alpine3.7
COPY . /esp-update-server
WORKDIR /esp-update-server
RUN pip install -r requirements.txt
EXPOSE 5000
CMD python3 ./server.py