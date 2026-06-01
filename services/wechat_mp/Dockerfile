FROM python:3.14-slim

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary

# Install omodul + oprim from local paths (adjust for prod)
# RUN pip install omodul oprim

COPY ../../src /app/src
COPY main.py /app/main.py

ENV PYTHONPATH=/app/src
WORKDIR /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9308"]
