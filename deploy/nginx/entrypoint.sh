#!/bin/sh
set -e

: "${PORT:=8000}"

envsubst '${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
exec nginx -g 'daemon off;'
