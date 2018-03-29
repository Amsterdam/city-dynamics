#!/bin/sh

set -e
set -u
set -x

DIR="$(dirname $0)"

dc() {
    docker-compose -p cityd${ENVIRONMENT} -f ${DIR}/docker-compose.yml $*
}

# trap 'dc kill ; dc rm -f' EXIT

rm -rf ${DIR}/backups
mkdir -p ${DIR}/backups

dc stop
dc rm
dc down
dc pull
dc build

dc up -d database
dc run --rm importer bash /app/deploy/docker-wait.sh
dc run --rm importer bash /app/run_import.sh
dc run --rm api python manage.py migrate

dc run --rm analyzer

dc exec -T database backup-db.sh citydynamics
