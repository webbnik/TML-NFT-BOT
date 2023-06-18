FROM python:slim-buster

RUN apt update && apt install -y nano sqlite3

RUN groupadd --gid 5005 pythongroup
RUN useradd --uid 5060 --gid pythongroup --home /app pythonuser

RUN mkdir /app

WORKDIR /app

COPY . .

RUN chown -R pythonuser.pythongroup /app

RUN pip3 install -r requirements.txt

USER pythonuser

EXPOSE 8000

CMD ["bash", "-c", "flask db init || true && flask db migrate && flask db upgrade && gunicorn -b 0.0.0.0:8000 --statsd-host=statsd-exporter-service:9125 --statsd-prefix=tml_nft_bot -w 2 --timeout 10 --preload app:app"]