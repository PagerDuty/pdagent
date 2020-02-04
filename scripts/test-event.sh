#!/bin/sh
. $(dirname $0)/../integration_tests/util.sh
bin/pd-send -k $SVC_KEY -t trigger -d "Hello I am test"
