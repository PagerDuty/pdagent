vagrant destroy -f agent-minimal-ubuntu1404
vagrant up agent-minimal-ubuntu1404
vagrant ssh agent-minimal-ubuntu1404 -c 'bash /vagrant/scripts/install_pub_ubuntu_pkg.sh'
