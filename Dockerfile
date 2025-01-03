FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    libz-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip3 install -U pip wheel
RUN pip3 install -r requirements.txt

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "entry.py", "--server.port=8501", "--server.address=0.0.0.0", "--", "--user_db_path=user_db.db", "--task_configs=./mini-test_config.json"]
