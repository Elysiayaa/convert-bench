FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Pandoc 负责文档转换，XeLaTeX 与 Noto 字体负责生成支持中文的 PDF。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        pandoc \
        texlive-xetex \
        texlive-lang-chinese \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /app/data /app/storage/uploads /app/storage/outputs /app/storage/datasets

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
