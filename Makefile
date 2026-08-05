.PHONY: test secret-scan package

test:
	./tests/run.sh

secret-scan:
	./scripts/linux/secret-scan.sh .

package: test secret-scan
	./scripts/linux/package-release.sh
