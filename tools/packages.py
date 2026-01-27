from argparse import ArgumentParser, Namespace
from email.parser import HeaderParser
import json
import os
import subprocess


def get_apt_packages() -> dict:
    """Get the installed apt packages in the target environment"""
    process = subprocess.run('dpkg --get-selections | grep -v deinstall', capture_output=True, text=True, shell=True)
    package_names = [line.split()[0] for line in process.stdout.splitlines()]
    packages = {}
    for package_name in package_names:
        process = subprocess.run(f'dpkg -L {package_name}', capture_output=True, text=True, shell=True)
        filenames = sorted(filename.strip() for filename in process.stdout.splitlines() if os.path.isfile(filename.strip()))
        files = {filename: os.path.getsize(filename) for filename in filenames}
        packages[package_name] = {
            'size': sum(files.values()) if files else 0,
            'files': files,
        }
    return packages


def get_pip_packages() -> dict:
    """Get the installed pip packages in the target environment"""
    process = subprocess.run('pip freeze  | sed s/=.*//', capture_output=True, text=True, shell=True)
    package_names = process.stdout.splitlines()
    packages = {}
    for package_name in package_names:
        process = subprocess.run(f'pip show --no-color --no-input --files {package_name}', capture_output=True, text=True, shell=True)
        header = HeaderParser().parsestr(process.stdout)
        filenames = sorted(filename.strip() for filename in header['Files'].splitlines() if os.path.isfile(os.path.join(header['Location'], filename.strip())))
        files = {filename: os.path.getsize(os.path.join(header['Location'], filename)) for filename in filenames}
        packages[package_name] = {
            'name': header['Name'],
            'version': header['Version'],
            'summary': header['Summary'],
            'location': header['Location'],
            'size': sum(files.values()) if files else 0,
            'requires': sorted(require.strip() for require in header['Requires'].split(', ') if require.strip()),
            'required': sorted(require.strip() for require in header['Required-by'].split(', ') if require.strip()),
            'files': files,
        }
    return packages


def get_packages() -> dict:
    """Get the installed packages in the target environment"""
    return {
        'apt': get_apt_packages(),
        'pip': get_pip_packages(),
    }


def parse_args() -> Namespace:
    """Parse the CLI arguments"""
    parser = ArgumentParser(description='Parse the packages currently installed on the system')
    parser.add_argument('out_path', type=os.path.abspath, help='path to output the packages list')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    packages = get_packages()
    with open(args.out_path, 'w') as file:
        json.dump(packages, file, indent=2)
