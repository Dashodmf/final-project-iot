FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY mqtt_sub.py .

CMD ["python", "mqtt_sub.py"]
