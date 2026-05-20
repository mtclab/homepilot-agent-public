FROM searxng/searxng:latest
USER root
COPY entrypoint.sh /usr/local/bin/secret-entrypoint.sh
RUN chmod +x /usr/local/bin/secret-entrypoint.sh
USER searxng
ENTRYPOINT ["secret-entrypoint.sh"]