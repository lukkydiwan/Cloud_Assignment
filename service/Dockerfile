FROM python:3.12-slim

WORKDIR /app

# Install CPU-only PyTorch wheel to keep image under 2 GB (avoids multi-GB CUDA libraries)
RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu

# Install pinned dependencies
COPY service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and schema (model weights are loaded dynamically from S3, NOT baked into image)
COPY data/schema.json /app/data/schema.json
COPY service/app.py /app/app.py

ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
