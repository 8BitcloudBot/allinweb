FROM python:3.12-slim

WORKDIR /app

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8003

# 端口可通过 TRIPPLAN_PORT 覆盖（默认 8003）
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${TRIPPLAN_PORT:-8003}"]
