include build-linux/make_common.env
export $(shell sed 's/=.*//' build-linux/make_common.env)

.PHONY: build
build: ubuntu centos

.PHONY: ubuntu
ubuntu: target/deb target/tmp/GPG-KEY-pagerduty

.PHONY: centos
centos: target/rpm target/tmp/GPG-KEY-RPM-pagerduty

.PHONY: build-ubuntu
build-ubuntu:
	docker build . \
		-t pdagent-ubuntu \
		-f Dockerfile-ubuntu \
		--build-arg FPM_VERSION="${FPM_VERSION}" \
		--build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
		--build-arg UBUNTU_VERSION="${UBUNTU_VERSION}" \
		--build-arg DOCKER_WORKDIR="${DOCKER_WORKDIR}"

.PHONY: build-centos
build-centos:
	docker build . \
		-t pdagent-centos \
		-f Dockerfile-centos-7 \
		--build-arg FPM_VERSION="${FPM_VERSION}" \
		--build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
		--build-arg CENTOS_VERSION="${CENTOS_VERSION}" \
		--build-arg DOCKER_WORKDIR="${DOCKER_WORKDIR}"

target/deb: build-ubuntu
	docker run \
		-v `pwd`:${DOCKER_WORKDIR} \
		-it pdagent-ubuntu \
			/bin/sh -c "/bin/sh build-linux/make_deb.sh ${DOCKER_WORKDIR}/build-linux/gpg-deb ${DOCKER_WORKDIR}/target"

target/rpm: build-centos
	docker run \
		-v `pwd`:${DOCKER_WORKDIR} \
		-it pdagent-centos \
			/bin/sh -c "/bin/sh build-linux/make_rpm.sh ${DOCKER_WORKDIR}/build-linux/gpg-rpm ${DOCKER_WORKDIR}/target"

target/tmp/GPG-KEY-pagerduty:
	docker run \
		-v `pwd`:${DOCKER_WORKDIR} \
		-it pdagent-ubuntu \
			/bin/sh -c "mkdir -p ${DOCKER_WORKDIR}/target/tmp; gpg --armor --export --homedir ${DOCKER_WORKDIR}/build-linux/gpg-deb > ${DOCKER_WORKDIR}/target/tmp/GPG-KEY-pagerduty"

target/tmp/GPG-KEY-RPM-pagerduty:
	docker run \
		-v `pwd`:${DOCKER_WORKDIR} \
		-it pdagent-ubuntu \
			/bin/sh -c "mkdir -p ${DOCKER_WORKDIR}/target/tmp; gpg --armor --export --homedir ${DOCKER_WORKDIR}/build-linux/gpg-rpm > ${DOCKER_WORKDIR}/target/tmp/GPG-KEY-RPM-pagerduty"

.PHONY: test
test:
	find unit_tests -name "test_*.py" | xargs python run-tests.py

.PHONY: test-integration
test-integration: test-integration-ubuntu test-integration-centos

.PHONY: test-integration-ubuntu
test-integration-ubuntu: ubuntu
	scripts/full-integration-test.sh ubuntu

.PHONY: test-integration-centos
test-integration-centos: centos
	scripts/full-integration-test.sh centos

.PHONY: clean
clean:
	rm -rf dist
	rm -rf target
	rm unit_tests/test_filelock_lock.txt
