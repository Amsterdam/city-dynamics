#!/usr/bin/env bash

set -u
set -e
set -x

echo 0.0.0.0:5432:citydynamics:citydynamics:insecure > ~/.pgpass

chmod 600 ~/.pgpass

# dump occupation data
pg_dump  -t google_raw_locations_realtime_current_* \
	 -Fc \
	 -U citydynamics \
	 -h 0.0.0.0 -p 5432 \
	 -f /tmp/backups/current.dump \
	 citydynamics
