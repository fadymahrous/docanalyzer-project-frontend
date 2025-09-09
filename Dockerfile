FROM python:3.12-slim
# Safer defaults & smaller images
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
#Update the Repo
RUN apt-get update && apt-get install -y --no-install-recommends \
     build-essential gcc iputils-ping\
  && rm -rf /var/lib/apt/lists/*

# Create an unprivileged user with a home dir for the application
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app

# Make /app owned by app user, to write logs freely
RUN chown app:app /app

# Use a dedicated virtualenv owned by root but usable by app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install deps first for better caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the app and ensure permissions
COPY --chown=app:app . .

# Expose port 8000
EXPOSE 80

# Go Normandy
USER app
CMD ["uvicorn", "django_main.asgi:application", "--host", "0.0.0.0", "--port", "80"]
