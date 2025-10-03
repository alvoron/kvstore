FROM python:3.11-slim

WORKDIR /app

# Copy kvstore source
COPY . /app

# Install
RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 5555

# Entry point (will be overridden by StatefulSet)
CMD ["python", "-m", "kvstore.cli.server_cli"]
