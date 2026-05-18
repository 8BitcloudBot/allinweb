FROM python:3.12-slim

WORKDIR /app

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV HF_ENDPOINT=https://hf-mirror.com

COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn neo4j pymilvus openai langchain-core langchain-huggingface sentence-transformers rank-bm25 jieba python-dotenv numpy pydantic slowapi langchain-text-splitters langchain-community

COPY . .

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
