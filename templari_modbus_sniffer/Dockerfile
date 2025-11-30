FROM python:3.11-slim

WORKDIR /app

COPY templari_sniffer.py /app/
COPY run.sh /app/
RUN pip install paho-mqtt
RUN apt-get update && apt-get install -y jq

RUN chmod +x /app/run.sh

CMD [ "/app/run.sh" ]

