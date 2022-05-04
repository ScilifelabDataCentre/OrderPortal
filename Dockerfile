# XXX Needs to be looked at: is gunicorn to be used?  tornado is the app web server!

FROM python:alpine

RUN apk update && apk upgrade

COPY ./requirements.txt /requirements.txt
RUN pip install -r /requirements.txt gunicorn
COPY ./orderportal /code/orderportal
RUN mkdir /code/site
WORKDIR /code/orderportal
ENV PYTHONPATH /code

ENV GUNICORN_CMD_ARGS "--bind=0.0.0.0:8000 --workers=1 --thread=4 --worker-class=gthread --forwarded-allow-ips='*' --access-logfile -"
CMD ["gunicorn", "app_orderportal:app"]

VOLUME ["/code/site"]
