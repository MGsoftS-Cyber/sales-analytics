FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/workspace SPARK_LOCAL_IP=127.0.0.1
WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY generator generator
COPY pipeline pipeline
RUN useradd -u 10001 -m analytics && mkdir -p /data && chown analytics /data
USER analytics
EXPOSE 8000
CMD ["uvicorn","app.api:app","--host","0.0.0.0","--port","8000"]
