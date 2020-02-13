#!/bin/bash
set -e

for test in $(dirname $0)/test_*.sh ; do 
  test_name=$(basename $test)
  echo -e "\n\n ---------------->   Running $test_name   <---------------- \n\n "
  set +x
  source $test
  set +x
  echo -e "\n\n---------------->   Succesfully Ran $test_name   <---------------- \n\n"
done
