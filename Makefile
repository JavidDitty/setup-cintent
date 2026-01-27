DISTPATH = ./bin
WORKPATH = ./local/build
SPECPATH = ./local

build:
	pyinstaller \
		--name "packages" \
		--clean \
		--onefile \
		--workpath ${WORKPATH} \
		--distpath ${DISTPATH} \
		--specpath ${SPECPATH} \
		./tools/packages.py
	pyinstaller \
		--name "pyfunctions" \
		--clean \
		--onefile \
		--workpath ${WORKPATH} \
		--distpath ${DISTPATH} \
		--specpath ${SPECPATH} \
		./tools/pyfunctions.py
