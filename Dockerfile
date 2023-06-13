FROM python:slim-buster

RUN groupadd --gid 5005 pythongroup
RUN useradd --uid 5060 --gid pythongroup --home /app pythonuser

RUN mkdir /app

WORKDIR /app

COPY . .

RUN chown -R pythonuser.pythongroup /app

RUN pip3 install -r requirements.txt

USER pythonuser

EXPOSE 8457

CMD [ "python", "-u", "./app.py" ]
