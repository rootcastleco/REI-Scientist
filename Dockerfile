FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/rei-scientist
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps . && useradd --create-home --shell /usr/sbin/nologin rei
USER rei
WORKDIR /workspace
ENTRYPOINT ["rei-scientist"]
CMD ["--help"]
