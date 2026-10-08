FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py bot.py db.py llm.py ./

ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]