# stratum-docs — PDF/EPUB → MD/DOCX 转换微服务
# 引擎: oprim parse_pdf(pdf_inspector/opendataloader, 最新集成, 无 docling)
#       fallback markitdown; fitz + python-docx(全页图 DOCX)
FROM python:3.14-slim

WORKDIR /srv

# 系统依赖(pymupdf 需要; PIL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 平台包 3O(oprim 转换引擎; 挂载或 COPY — 构建时 COPY 进镜像)
COPY 3O/ /opt/platform/
ENV PYTHONPATH=/opt/platform:/opt/platform/obase:/opt/platform/oskill:/opt/platform/oprim:/opt/platform/oservi:/opt/platform/omodul

# Python 依赖
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

# 服务代码
COPY services/docs_service/ /srv/docs_service/
COPY services/docs_service/run.sh /srv/run.sh
RUN chmod +x /srv/run.sh

EXPOSE 8300
CMD ["/srv/run.sh"]
