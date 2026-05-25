# Pin to v2.4.0 — :latest fails on x86_64 with numpy arch mismatch (#75)
FROM rhasspy/wyoming-piper:v2.4.0

RUN .venv/bin/pip3 install --no-cache-dir 'wyoming[http]'

COPY entrypoint.sh /usr/src/entrypoint.sh
RUN chmod +x /usr/src/entrypoint.sh

EXPOSE 10200 5000

ENTRYPOINT ["/usr/src/entrypoint.sh"]