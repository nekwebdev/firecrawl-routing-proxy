FROM docker.io/searxng/searxng:2026.4.24-a7ac696b4

USER root
RUN cp /usr/local/searxng/entrypoint.sh /usr/local/searxng/entrypoint-base.sh

COPY settings.yml /etc/searxng/settings.yml
COPY entrypoint.sh /usr/local/searxng/entrypoint.sh

RUN chmod 0755 /usr/local/searxng/entrypoint.sh /usr/local/searxng/entrypoint-base.sh
USER searxng

ENTRYPOINT ["/usr/local/searxng/entrypoint.sh"]
