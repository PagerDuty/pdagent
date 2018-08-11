vagrant destroy -f agent-minimal-ubuntu1204
vagrant up agent-minimal-ubuntu1204
scons local-repo gpg-home=build-linux/gnupg virt=agent-minimal-ubuntu1204
