# OpsMate UI — python:3.12-slim, non-root, Streamlit on 8501.
# Multi-arch base, same as the app (the M3 portability rule).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .

RUN useradd --create-home --uid 10002 opsmate && chown -R opsmate:opsmate /app
USER opsmate

EXPOSE 8501
# --server.address 0.0.0.0 so the published port reaches it; headless so it does
# not try to open a browser inside the container.
CMD ["streamlit", "run", "app.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8501", \
     "--server.headless", "true", \
     "--browser.gatherUsageStats", "false"]
