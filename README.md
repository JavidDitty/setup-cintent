# setup-cintent

Set up your GitHub Actions workflow for [CIntent](https://github.com/JavidDitty/cintent).

## Table of Contents

- [Usage](#usage)
- [License](#license)

## Usage

### Manual Upload

```yaml
steps:
- uses: actions/checkout@v4

- name: Set up Python ${{ matrix.python-version }}
  uses: actions/setup-python@v5
  with:
    python-version: ${{ matrix.python-version }}

- uses: JavidDitty/setup-cintent@v1

# Insert your other steps here

- name: Upload CIntent Artifacts
  uses: actions/upload-artifact@v4
  with:
    name: ${{ env.CINTENT_ARTIFACT_NAME }}
    path: ${{ env.CINTENT_LOGS }}
```

### Automatic Upload

```console
TBD
```
