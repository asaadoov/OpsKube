# frontend/Dockerfile
FROM nginx:1.25-alpine

RUN rm -rf /usr/share/nginx/html/*

COPY nginx.conf /etc/nginx/nginx.conf
COPY public /usr/share/nginx/html

EXPOSE 80
