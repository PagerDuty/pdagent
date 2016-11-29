vagrant destroy -f agent-minimal-ubuntu1204
vagrant up agent-minimal-ubuntu1204
vagrant ssh agent-minimal-ubuntu1204 -c 'bash /vagrant/scripts/install_pub_ubuntu_pkg.sh'
