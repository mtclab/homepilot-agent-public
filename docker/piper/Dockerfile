FROM rhasspy/wyoming-piper:latest

RUN .venv/bin/pip3 install --no-cache-dir 'wyoming[http]'

COPY entrypoint.sh /usr/src/entrypoint.sh
RUN chmod +x /usr/src/entrypoint.sh

EXPOSE 10200 5000

ENTRYPOINT ["/usr/src/entrypoint.sh"]