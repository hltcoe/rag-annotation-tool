#syntax=docker/dockerfile:1.7-labs
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    libz-dev \
    && rm -rf /var/lib/apt/lists/*

# Make a directory someplace with resources, outputs etc,
# bind mount it to the container as /app/data, and update the task
# config to point into that directory.
COPY --exclude=venv --exclude=data --exclude=resources --exclude=outputs . .

RUN pip3 install -U pip wheel
RUN pip3 install -r requirements.txt

# Otherwise you have to download the datasets every time you
# start the container
ENV IR_DATASETS_HOME=/app/data/ir_datasets

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "entry.py", \
           "--", \
           "--user_db_path=data/user_db.db", \
           "--task_configs=data/mini-test_config.json"]
