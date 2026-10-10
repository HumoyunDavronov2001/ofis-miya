FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Tashkent \
    MIYA_HOST=0.0.0.0 MIYA_PORT=8090 MIYA_BAZA=/data/miya.db MIYA_PROXY=1
# ffmpeg — ovozli xabarni Google kutgan formatga o'girish (bo'lmasa ovoz jimgina buziladi); tzdata — Toshkent vaqti
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10003 --no-create-home miya \
    && mkdir -p /data && chown miya /data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY miya ./miya
COPY veb ./veb
COPY dizayn/shrift ./dizayn/shrift
# tasvir yig'ilganda kerakli dasturlar borligini tekshirish
RUN command -v ffmpeg && command -v ffprobe && python3 -c "import miya.veb"
USER miya
VOLUME ["/data"]
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/api/holat', timeout=4)"
CMD ["python3", "-m", "miya"]
