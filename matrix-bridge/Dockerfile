FROM python:3.12-alpine
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bridge.py .
RUN adduser -D -u 1000 bridgeuser
USER bridgeuser
CMD ["python", "-u", "bridge.py"]