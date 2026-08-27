# Team Preferences & Best Practices

- **Zero Data Retention**: Deploy on Regolo.ai EU-sovereign inference.
- **Testing**: Use pytest fixtures with automatic database transaction rollback.
- **Logging**: Structured JSON logging (`structlog`), no raw passwords or auth tokens in stdout.
- **Git & PRs**: Reference relevant ADR numbers in PR descriptions.
