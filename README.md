# setup-cintent

Set up your GitHub Actions workflow for [CIntent](https://github.com/JavidDitty/cintent).

## Usage

```yaml
steps:
- uses: actions/checkout@VERSION

- uses: JavidDitty/setup-cintent@v1

# Insert your other steps here

- name: Upload CIntent Artifacts
  uses: actions/upload-artifact@VERSION
  if: always()
  with:
    name: ${{ env.CINTENT_ARTIFACT_NAME }}
    path: ${{ env.CINTENT_LOGS }}
```
