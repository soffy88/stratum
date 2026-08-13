# stratum-docs — PDF/EPUB → MD/DOCX 转换微服务
# 引擎: oprim parse_pdf(pdf_inspector/opendataloader, 最新集成, 无 docling)
#       fallback markitdown; fitz + python-docx(全页图 DOCX)
# 平台包 3O 经 compose 挂载 /opt/platform(宿主 /home/soffy/deploy/3O, 避免重复打镜像)
FROM python:3.14-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    fonts-noto-cjk fontconfig nodejs npm \
    && npm install -g officecli --registry https://registry.npmmirror.com \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/opt/platform:/opt/platform/obase:/opt/platform/oskill:/opt/platform/oprim:/opt/platform/oservi:/opt/platform/omodul

COPY deploy/docs_service/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY services/docs_service/ /srv/docs_service/
COPY services/docs_service/run.sh /srv/run.sh
# officecli 配置(external + NIM 端点; 经 compose 代理出网)
COPY deploy/docs_service/officecli_config.json /srv/officecli_config.json
RUN mkdir -p /root/.config/officecli && cp /srv/officecli_config.json /root/.config/officecli/config.json
RUN chmod +x /srv/run.sh

EXPOSE 8300
CMD ["/srv/run.sh"]
