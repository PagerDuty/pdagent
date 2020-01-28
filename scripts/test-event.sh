#!/bin/sh
. $(dirname $0)/../pdagenttestinteg/util.sh
bin/pd-send -k $SVC_KEY -t trigger -d "Hello I am test"
