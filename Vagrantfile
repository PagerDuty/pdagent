# -*- mode: ruby -*-
# vi: set ft=ruby :


vms = {
    "agent-centos58"    =>  {
        "box"       => "centos58",
        "box_url"   => "http://tag1consulting.com/files/centos-5.8-x86-64-minimal.box",
    },
    "agent-centos64"    =>  {
        "box"       => "centos64",
        "box_url"   => "http://developer.nrel.gov/downloads/vagrant-boxes/CentOS-6.4-i386-v20130731.box",
    },
    "agent-lucid32"    =>  {
        "box"       => "lucid32",
        "box_url"   => "http://files.vagrantup.com/lucid32.box",
    },
    "agent-precise32"    =>  {
        "box"       => "precise32",
        "box_url"   => "http://files.vagrantup.com/precise32.box",
    },
}


Vagrant::Config.run do |config|

    vms.each do |name, conf|
        config.vm.define name do |conf2|
            conf2.vm.box = conf["box"]
            conf2.vm.box_url = conf["box_url"]
            conf2.vm.network :bridged
        end
    end
end

