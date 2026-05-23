<p align="center">
  <img src="https://raw.githubusercontent.com/hendurhance/koel/main/docs/images/koel-logo.png" alt="Koel" width="220" />
</p>

# Koel

Self-hostable exchange-rate API with consensus scraping, partitioned history, and API-key-based access. This image runs the **API, Celery worker, and Celery beat** (one image, different commands).

- **Source & full docs:** https://github.com/hendurhance/koel
- **Dashboard image:** https://hub.docker.com/r/hendurhance/koel-frontend
- **Tags:** `1.0.0`, `latest` — multi-arch (`linux/amd64`, `linux/arm64`)

## Run

Koel needs Postgres + Redis. The quickest path is the published compose file:

```bash
git clone https://github.com/hendurhance/koel.git && cd koel
cp .env.example .env          # set APP_SECRET + SMTP_*
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml exec api koel db seed
```

API at `:8000`, dashboard at `:3000`. Configuration and the full API reference live in the repo.

## License

[Elastic License 2.0](https://github.com/hendurhance/koel/blob/main/LICENSE) — free to use, self-host, modify, and run commercially; you may not offer Koel to others as a hosted or managed service.
