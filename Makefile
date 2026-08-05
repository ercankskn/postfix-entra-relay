.PHONY: test lint secret-scan package

test:
	./tests/run.sh

lint:
	python3 -m py_compile src/*.py dashboard/*.py
	bash -n scripts/linux/*.sh

secret-scan:
	./scripts/linux/secret-scan.sh .

package: test secret-scan
	./scripts/linux/package-release.sh
