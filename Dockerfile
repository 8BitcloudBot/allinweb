FROM python:3.12-slim

WORKDIR /app

ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

COPY pyproject.toml uv.lock ./
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple uv && uv sync

COPY . .
RUN mkdir -p runtime

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "chefmate.server:app", "--host", "0.0.0.0", "--port", "8000"]
