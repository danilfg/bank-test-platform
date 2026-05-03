FROM alpine:3.20 AS assets

RUN mkdir -p /assets \
    && wget -O /assets/asyncapi.css https://unpkg.com/@asyncapi/react-component@1.2.24/styles/default.min.css \
    && wget -O /assets/asyncapi.js https://unpkg.com/@asyncapi/react-component@1.2.24/browser/standalone/index.js

FROM nginx:1.27-alpine

COPY --from=assets /assets/asyncapi.css /usr/share/nginx/html/assets/asyncapi.css
COPY --from=assets /assets/asyncapi.js /usr/share/nginx/html/assets/asyncapi.js
COPY infra/asyncapi/index.html /usr/share/nginx/html/index.html
COPY docs/asyncapi.yaml /usr/share/nginx/html/asyncapi.yaml
