#!/bin/sh
sleep ${1}
perl core.pl -qe >>../log/cron.log 2>&1
