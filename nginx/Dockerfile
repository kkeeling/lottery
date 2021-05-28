FROM nginx:1.17

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d
RUN mkdir -p /etc/nginx/ssl/
RUN date
COPY dhparam.pem /etc/nginx/ssl/