DISTPATH = ./bin
WORKPATH = ./local/build
SPECPATH = ./local

build:
	pyinstaller \
		--name "pyfunctions" \
		--clean \
		--onefile \
		--workpath ${WORKPATH} \
		--distpath ${DISTPATH} \
		--specpath ${SPECPATH} \
		./bin/pyfunctions.py
