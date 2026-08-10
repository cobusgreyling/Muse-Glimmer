FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY data ./data
COPY assets ./assets
COPY static ./static

ENV HOST=0.0.0.0
ENV PORT=7870

EXPOSE 7870
CMD ["python", "app.py"]
