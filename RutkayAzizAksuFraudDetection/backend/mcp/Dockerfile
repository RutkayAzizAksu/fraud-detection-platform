FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the standard SSE port for the MCP Server
EXPOSE 8000

# Start the MCP server
CMD ["python", "-u", "main.py"]
