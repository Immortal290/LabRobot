FROM python:3.11-slim

WORKDIR /app

RUN pip install websockets

COPY . .

CMD ["python", "-u", "ros2_bridge.py"]
