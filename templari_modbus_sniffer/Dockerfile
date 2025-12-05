FROM python:3.11-slim

WORKDIR /app

COPY templari_sniffer.py /app/
COPY modbus_parsing.py /app/
COPY templari_sniffer.py /app/

RUN pip install --no-cache-dir paho-mqtt

RUN chmod +x /app/templari_sniffer.py

CMD [ "python3", "/app/templari_sniffer.py" ]

