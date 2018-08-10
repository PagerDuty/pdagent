# -*- mode: ruby -*-
# vi: set ft=ruby :

_bento_centos65 = {
  "box"       => "bento_centos65",
  "box_url"   => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_centos-6.5_chef-provisionerless.box",
}
_bento_centos72 = {
  "box"       => "bento_centos72",
  "box_url"   => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_centos-7.2_chef-provisionerless.box",
}
_bento_ubuntu1204 = {
  "box"       => "bento_ubuntu1204",
  "box_url"   => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_ubuntu-12.04_chef-provisionerless.box",
}
_bento_ubuntu1404 = {
  "box"       => "bento_ubuntu1404",
  "box_url"   => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_ubuntu-14.04_chef-provisionerless.box",
}
_bento_ubuntu1604 = {
  "box"       => "bento_ubuntu1604",
  "box_url"   => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_ubuntu-16.04_chef-provisionerless.box",
}

vms = {
  "agent-minimal-centos65"    => _bento_centos65,
  "agent-minimal-centos72"    => _bento_centos72,
  "agent-minimal-ubuntu1204"  => _bento_ubuntu1204,
  "agent-minimal-ubuntu1404"  => _bento_ubuntu1404,
  "agent-minimal-ubuntu1604"  => _bento_ubuntu1604
}

Vagrant.configure("2") do |conf_outer|

  vms.each do |name, conf|

    conf_outer.vm.define name do |config|

      config.vm.box = conf["box"]
      config.vm.box_url = conf["box_url"]

      # Public/bridged network so VM can install packages from the internet
      config.vm.network :public_network, :bridge => "en0: Wi-Fi (AirPort)"

    end # conf_outer.vm.define

  end # vms.each

end # Vagrant.configure
