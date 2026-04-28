FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY mainv2.py .

CMD ["uvicorn", "mainv2:app", "--host", "0.0.0.0", "--port", "8000"]