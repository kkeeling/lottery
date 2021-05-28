#!/bin/bash
#
# Daily PostgreSQL maintenance: vacuuming and backuping.
#
##
set -e
echo "[`date`] Maintaining $1"
echo 'VACUUM' | psql -U lottery -hlocalhost -d $1
DUMP="/opt/data/$2"
pg_dump -U lottery -hlocalhost $1 | gzip -c > $2