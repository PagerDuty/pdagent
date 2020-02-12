set -e

for test in $(dirname $0)/test_*.sh ; do 
  test_name=$(basename $test)
  echo ; echo
  echo "---------------->   Running $test_name <----------------" ; echo ; echo
  set +x
  source $test
  set +x
  echo ; echo
  echo "---------------->   Succesfully Ran $test_name <----------------"
done
