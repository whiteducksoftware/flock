FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8088 \
    FLOCK_AUTO_TRACE=false

WORKDIR /app

# The whole build context: ./wheels is optional (git-ignored) and holds a
# pre-release flock-core wheel; without it pip only warns and uses PyPI.
COPY . ./
RUN pip install --no-cache-dir --find-links ./wheels -r requirements.txt \
    && rm -rf ./wheels

EXPOSE 8088

# Precompile bytecode so cold starts don't pay for it (as in the official samples).
RUN PYTHONDONTWRITEBYTECODE= python -m compileall -q $(python -c "import sysconfig as s; print(s.get_paths()['stdlib'], s.get_paths()['purelib'])") || true; \
    PYTHONDONTWRITEBYTECODE= python -m compileall -q .

CMD ["python3", "main.py"]
