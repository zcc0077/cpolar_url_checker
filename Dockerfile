FROM python:3.10 AS build

RUN mkdir /install
WORKDIR /install
RUN python3 -m pip install --upgrade pip \
    && pip install lxml requests bs4 charset_normalizer --target=/install

FROM python:3.10-alpine
COPY --from=build /install /usr/local
COPY app.py /app/
WORKDIR /app

ENV PYTHONPATH=/usr/local

CMD ["python3", "app.py"]
