#!/bin/bash

docker run -it -d \
       --name rag \
       -p 8501:8501 \
       --mount type=bind,source="$(pwd)"/data,target=/app/data \
       streamlit
