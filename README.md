# Create Tag Action (Python Composite)

Reimplementação em Python da action `Basecone-GHA-CreateTag` usando uma composite action.

## Inputs
Mesmos que a versão original:
- `github_token` (obrigatório)
- `user_tag`
- `default_bump` (major|minor|patch|prerelease) default: patch
- `tag_suffix`
- `tag_prefix`
- `prereleaseIdentifier` (true/false) default: true
- `fetch_all_tags` (true/false)
- `is_dry_run` (true/false)

## Outputs
- `tag`  Tag final criada (ou simulada se dry run)
- `version` Valor sem o `v` inicial (mantém prefix se usado)

## Uso
```yaml
- name: Create tag (Python)
  uses: Basecone/Basecone-GHA-CreateTag-Python@v1
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    default_bump: patch
```

## Notas
- Usa PyGithub para interação com API.
- Faz coerção simples de tags já existentes.
- Em prerelease: se existir já prerelease com mesmo identificador incrementa número, senão inicia `<id>.1`.
