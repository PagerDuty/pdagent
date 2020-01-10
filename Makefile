include build-linux/make_common.env
export $(shell sed 's/=.*//' build-linux/make_common.env)

main: build

build: ubuntu centos

ubuntu: target/deb target/tmp/GPG-KEY-pagerduty

centos: target/rpm target/tmp/GPG-KEY-pagerduty

build-ubuntu:
	docker build . \
		-t pdagent-ubuntu \
		-f Dockerfile-ubuntu \
		--build-arg FPM_VERSION="${FPM_VERSION}" \
		--build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
		--build-arg UBUNTU_VERSION="${UBUNTU_VERSION}"

build-centos:
	docker build . \
		-t pdagent-centos \
		-f Dockerfile-centos-7 \
		--build-arg FPM_VERSION="${FPM_VERSION}" \
		--build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
		--build-arg CENTOS_VERSION="${CENTOS_VERSION}"

target/deb: build-ubuntu
	docker run \
		-v `pwd`:/pdagent \
		-it pdagent-ubuntu \
			/bin/sh -c "/bin/sh build-linux/make_deb.sh /pdagent/tmp/gnupg /pdagent/target"

target/rpm: build-centos
	docker run \
		-v `pwd`:/pdagent \
		-it pdagent-centos \
			/bin/sh -c "/bin/sh build-linux/make_rpm.sh /pdagent/tmp/gnupg /pdagent/target"

target/tmp/GPG-KEY-pagerduty:
	docker run \
		-v `pwd`:/pdagent \
		-it pdagent-ubuntu \
			/bin/sh -c "mkdir -p /pdagent/target/tmp; gpg --armor --export --homedir /pdagent/tmp/gnupg > /pdagent/target/tmp/GPG-KEY-pagerduty"

clean:
	rm -rf dist
	rm -rf target
