vagrant destroy -f agent-minimal-ubuntu1604
vagrant up agent-minimal-ubuntu1604
vagrant ssh agent-minimal-ubuntu1604 -c 'bash /vagrant/scripts/install_pub_ubuntu_pkg.sh'
