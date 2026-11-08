FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir boto3 requests

COPY worker/worker.py /app/worker.py
COPY prompts/ /app/prompts/

ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/worker.py"]
