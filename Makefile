dev:
\tdocker compose -f deploy/docker-compose.yml up --build

prod:
\tdocker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml up --build -d

down:
\tdocker compose down
