vagrant destroy -f agent-minimal-centos72
vagrant up agent-minimal-centos72
vagrant ssh agent-minimal-centos72 -c 'bash /vagrant/scripts/install_pub_centos_pkg.sh'
