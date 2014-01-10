# -*- mode: ruby -*-
# vi: set ft=ruby :


_bento_centos65 = {
    "box"       => "bento_centos65",
    "box_url"   => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_centos-6.5_chef-provisionerless.box",
}
_bento_ubuntu1004 = {
    "box"       => "bento_ubuntu1004",
    "box_url"   => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_ubuntu-10.04_chef-provisionerless.box",
}
_bento_ubuntu1204 = {
    "box"       => "bento_ubuntu1204",
    "box_url"   => "http://opscode-vm-bento.s3.amazonaws.com/vagrant/virtualbox/opscode_ubuntu-12.04_chef-provisionerless.box",
}

vms = {
    "agent-minimal-centos65"    => _bento_centos65,
    "agent-minimal-ubuntu1004"  => _bento_ubuntu1004,
    "agent-minimal-ubuntu1204"  => _bento_ubuntu1204,
    "agent-zabbix-centos65"     => _bento_centos65,
    "agent-zabbix-ubuntu1004"   => _bento_ubuntu1004,
    "agent-zabbix-ubuntu1204"   => _bento_ubuntu1204,
}


Vagrant.configure("2") do |conf_outer|

    vm_num = 0

    vms.each do |name, conf|

        vm_num += 1
        vm_num_snapshot = vm_num # snapshot the value in this scope

        conf_outer.vm.define name do |config|

            config.vm.box = conf["box"]
            config.vm.box_url = conf["box_url"]

            # Public/bridged network so VM can install packages from the internet
            config.vm.network :public_network, :bridge => "en0: Wi-Fi (AirPort)"

            if name.starts_with? "agent-zabbix-"

                # vagrant-omnibus will install chef
                config.omnibus.chef_version = :latest

                server_ip = "127.0.0.1"

                #config.vm.forward_port 80, (8080 + vm_num_snapshot)

                ## CentOS64 box has iptables blocking all traffic - allow http
                #config.vm.provision "shell",
                #    inline: "sudo iptables -I INPUT 2 -p tcp --dport 80 -j ACCEPT"

                config.vm.provision :chef_solo do |chef|
                    chef.json = {
                      :mysql => {
                        :server_root_password => 'rootpass',
                        :server_debian_password => 'debpass',
                        :server_repl_password => 'replpass'
                      },
                      'postgresql' => {
                        'password' => {
                          'postgres' => 'rootpass'
                        }
                      },
                      'zabbix' => {
                        'agent' => {
                          'servers' => [server_ip],
                          'servers_active' => [server_ip]
                        },
                        'web' => {
                          'install_method' => 'apache',
                          'fqdn' => server_ip
                        },
                        'server' => {
                          'install' => true,
                          'ipaddress' => server_ip
                        },
                        'database' => {
                          #'dbport' => '5432',
                          #'install_method' => 'postgres',
                          'dbpassword' => 'password123'
                        }
                      }
                    }

                    chef.add_recipe "database::mysql"
                    chef.add_recipe "mysql::server"
                    chef.add_recipe "zabbix"
                    chef.add_recipe "zabbix::database"
                    chef.add_recipe "zabbix::server"
                    chef.add_recipe "zabbix::web"
                    #chef.add_recipe "zabbix::agent_registration"

                    #chef.log_level = :debug
                end

            end # zabbix

        end # conf_outer.vm.define

    end # vms.each

end # Vagrant.configure

