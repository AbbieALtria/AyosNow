FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN DJANGO_DEBUG=true DATABASE_URL=sqlite:///db.sqlite3 python manage.py collectstatic --noinput

USER appuser

EXPOSE 8000

CMD ["python", "start.py"]
