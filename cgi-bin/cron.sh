#!/bin/sh
sleep ${1}
nice -n 10 perl core.pl -qe >>../log/cron.log 2>&1
