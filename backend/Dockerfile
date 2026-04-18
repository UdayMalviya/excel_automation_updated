FROM mcr.microsoft.com/playwright/python:v1.53.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DISPLAY=:99 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11-utils \
    x11vnc \
    fluxbox \
    novnc \
    websockify \
    net-tools \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY start.sh /app/start.sh
COPY src /app/src

RUN chmod +x /app/start.sh

EXPOSE 8000 5900 6080

CMD ["/app/start.sh"]
