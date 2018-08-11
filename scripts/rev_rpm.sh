vagrant destroy -f agent-minimal-centos65
vagrant up agent-minimal-centos65
scons local-repo gpg-home=build-linux/gnupg virt=agent-minimal-centos65
