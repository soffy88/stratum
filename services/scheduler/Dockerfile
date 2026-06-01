FROM python:3.14-slim

RUN pip install --no-cache-dir apscheduler psycopg2-binary

# Install omodul + oprim + oskill from local paths (adjust for prod)
# RUN pip install omodul oprim oskill

COPY ../../src /app/src
COPY main.py /app/main.py

ENV PYTHONPATH=/app/src
WORKDIR /app

CMD ["python", "main.py"]
