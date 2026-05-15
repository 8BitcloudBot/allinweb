FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync

COPY . .
RUN mkdir -p runtime

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "chefmate.server:app", "--host", "0.0.0.0", "--port", "8000"]
