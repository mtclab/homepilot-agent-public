FROM n8nio/n8n:1.98.0
USER root
COPY entrypoint.sh /usr/local/bin/custom-entrypoint.sh
RUN chmod +x /usr/local/bin/custom-entrypoint.sh
USER node
ENTRYPOINT ["custom-entrypoint.sh"]
CMD ["node", "/usr/local/bin/n8n"]