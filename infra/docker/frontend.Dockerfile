FROM nginx:1.27-alpine
COPY frontend/ /usr/share/nginx/html/
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
