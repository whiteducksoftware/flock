FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8088 \
    FLOCK_AUTO_TRACE=false

WORKDIR /app

# Flock from PyPI - or from a wheel placed in ./wheels before a release.
COPY requirements.txt ./
COPY wheels/ ./wheels/
RUN pip install --no-cache-dir --find-links ./wheels -r requirements.txt \
    && rm -rf ./wheels

COPY main.py ./

EXPOSE 8088

# Precompile bytecode so cold starts don't pay for it (as in the official samples).
RUN PYTHONDONTWRITEBYTECODE= python -m compileall -q $(python -c "import sysconfig as s; print(s.get_paths()['stdlib'], s.get_paths()['purelib'])") || true; \
    PYTHONDONTWRITEBYTECODE= python -m compileall -q .

CMD ["python3", "main.py"]
