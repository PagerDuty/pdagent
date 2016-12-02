vagrant destroy -f agent-minimal-centos65
vagrant up agent-minimal-centos65
vagrant ssh agent-minimal-centos65 -c 'bash /vagrant/scripts/install_pub_centos_pkg.sh'
