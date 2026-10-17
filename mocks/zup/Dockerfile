FROM python:3.12-slim
WORKDIR /app
COPY server.py data.json ./
EXPOSE 8001
CMD ["python", "-u", "server.py"]
