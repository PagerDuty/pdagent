# -*- mode: ruby -*-
# vi: set ft=ruby :

_box_centos64 = {
    "box"       => "centos64",
    "box_url"   => "http://developer.nrel.gov/downloads/vagrant-boxes/CentOS-6.4-i386-v20130731.box",
}
_box_lucid32 = {
    "box"       => "lucid32",
    "box_url"   => "http://files.vagrantup.com/lucid32.box",
}
_box_precise32 = {
    "box"       => "precise32",
    "box_url"   => "http://files.vagrantup.com/precise32.box",
}

vms = {
    "agent-minimal-centos64"    =>  _box_centos64,
    "agent-minimal-lucid32"     =>  _box_lucid32,
    "agent-minimal-precise32"   =>  _box_precise32,
    "agent-zabbix-centos64"     =>  _box_centos64,
    "agent-zabbix-lucid32"      =>  _box_lucid32,
    "agent-zabbix-precise32"    =>  _box_precise32,
}


Vagrant::Config.run do |conf_outer|

    vm_num = 0

    vms.each do |name, conf|

        vm_num += 1
        vm_num_snapshot = vm_num # snapshot the value in this scope

        conf_outer.vm.define name do |config|

            config.vm.box = conf["box"]
            config.vm.box_url = conf["box_url"]

            # Bridged network so VM can install packages from the internet
            config.vm.network :bridged, :bridge => "en0: Wi-Fi (AirPort)"

            if name.starts_with? "agent-zabbix-"
                server_ip = "127.0.0.1"

                config.vm.forward_port 80, (32080 + vm_num_snapshot * 100)
                ## CentOS64 box has iptables blocking all traffic - allow http
                #config.vm.provision "shell",
                #    inline: "sudo iptables -I INPUT 2 -p tcp --dport 80 -j ACCEPT"
=begin
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
=end
            end
        end
    end

end

