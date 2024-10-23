FROM python:3.10-slim

# Install Chrome and Chrome WebDriver dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    chromium \
    chromium-driver

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "src/main.py"]