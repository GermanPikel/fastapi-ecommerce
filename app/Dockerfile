FROM python:3.12-alpine

# устанавливаем переменные окружения
ENV HOME=/home/fast \
    APP_HOME=/home/fast/app \
    PYTHONPATH="$PYTHONPATH:/home/fast" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# создаем домашнюю директорию для пользователя(/home/fast) и директорию для проекта(/home/fast/app)
# создаем группу fast
# создаем отдельного пользователя fast
RUN mkdir -p $APP_HOME \
  && addgroup -S fast \
  && adduser -S fast -G fast

# устанавливаем рабочую директорию
WORKDIR $HOME

# копирование проекта FastAPI в рабочую директорию
COPY app app
COPY requirements.txt alembic.ini .env .

# установка базовых пакетов для сборки (могут понадобиться для некоторых Python пакетов)
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev \
    && apk add --no-cache postgresql-dev

# обновление pip с увеличенным таймаутом
# установка зависимостей из списка requirements.txt с увеличенным таймаутом
# изменение владельца, для всех директорий и файлов проекта, на пользователя fast
RUN pip install --upgrade pip \
 && pip --default-timeout=100 install -r requirements.txt \
 && chown -R fast:fast .

# удаление пакетов сборки для уменьшения размера образа
RUN apk del .build-deps

# изменение рабочего пользователя на fast
USER fast