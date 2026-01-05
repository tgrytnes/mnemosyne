# Mnemosyne Environments (Single-Host Dev/Staging/Prod)

This setup runs dev, staging, and prod on a single Raspberry Pi using Docker Compose.
Only one environment should be up at a time to avoid resource contention.

## Files and Conventions

- Base compose: `docker-compose.yml`
- Overrides: `docker-compose.dev.yml`, `docker-compose.staging.yml`, `docker-compose.prod.yml`
- Env files: `.env.dev`, `.env.staging`, `.env.prod`
- Compose project names: `mnemosyne-dev`, `mnemosyne-staging`, `mnemosyne-prod`

## Image Promotion

All environments use the same image, pinned by `IMAGE_TAG`.

Example flow:
1) Build and push image in CI with tag `vX.Y.Z` (or SHA).
2) Set `IMAGE_TAG` in `.env.staging` to `vX.Y.Z`.
3) Run staging, execute E2E tests, verify health.
4) Promote by setting the same `IMAGE_TAG` in `.env.prod`.
5) Roll back by setting `IMAGE_TAG` to a previous known-good tag.

## Commands

Start an environment:
```
make env-dev-up
make env-staging-up
make env-prod-up
```

Stop an environment:
```
make env-down ENV=dev
make env-down ENV=staging
make env-down ENV=prod
```

Check status:
```
make env-status ENV=staging
```

## Moving Staging or Prod to Another Host

1) Install Docker and Docker Compose on the new host.
2) Copy `docker-compose.yml`, the matching override file, and the env file.
3) Set `IMAGE_TAG` and secrets in the env file.
4) Run the same `make env-*-up` command on the new host.

## Notes

- Secrets must live in the env files or Docker secrets; do not hard-code them.
- Keep only one environment running on the Pi to avoid memory pressure.
