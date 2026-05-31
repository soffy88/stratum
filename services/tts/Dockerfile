FROM ghcr.io/swivid/f5-tts:main

# Install HTTP server deps into the existing conda environment
COPY requirements.txt /tmp/requirements.txt
RUN /opt/conda/bin/pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --timeout 120 \
    -r /tmp/requirements.txt

WORKDIR /app
COPY server.py /app/server.py

EXPOSE 9301

ENV PORT=9301

CMD ["/opt/conda/bin/python", "/app/server.py"]
