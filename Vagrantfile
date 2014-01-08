# -*- mode: ruby -*-
# vi: set ft=ruby :


vms = {
    "agent-centos64-zabbix"    =>  {
        "box"       => "centos64",
        "box_url"   => "http://developer.nrel.gov/downloads/vagrant-boxes/CentOS-6.4-i386-v20130731.box",
    },
    "agent-minimal-centos64"    =>  {
        "box"       => "centos64",
        "box_url"   => "http://developer.nrel.gov/downloads/vagrant-boxes/CentOS-6.4-i386-v20130731.box",
    },
    "agent-minimal-lucid32"    =>  {
        "box"       => "lucid32",
        "box_url"   => "http://files.vagrantup.com/lucid32.box",
    },
    "agent-minimal-precise32"    =>  {
        "box"       => "precise32",
        "box_url"   => "http://files.vagrantup.com/precise32.box",
    },
}


Vagrant::Config.run do |config|

    vms.each do |name, conf|
        config.vm.define name do |conf2|
            conf2.vm.box = conf["box"]
            conf2.vm.box_url = conf["box_url"]
            conf2.vm.network :bridged, :bridge => "en0: Wi-Fi (AirPort)"
        end
        if name == "agent-centos64-zabbix"
            server_ip = "127.0.0.1"
            config.vm.forward_port 80, 32080
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

        end
    end


end

