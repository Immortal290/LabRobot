FROM python:3.11-slim

WORKDIR /app

# Install requests for sending events to the backend
RUN pip install requests gpiozero

COPY . .

CMD ["python", "-u", "gpio_service.py"]
