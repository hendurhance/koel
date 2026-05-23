<p align="center">
  <img src="https://raw.githubusercontent.com/hendurhance/koel/main/docs/images/koel-logo.png" alt="Koel" width="220" />
</p>

# Koel — Dashboard

The Nuxt 3 dashboard for [**Koel**](https://hub.docker.com/r/hendurhance/koel), the self-hostable exchange-rate API. Ships as a standalone Nitro server that proxies to the Koel API.

- **Source & full docs:** https://github.com/hendurhance/koel
- **Backend image:** https://hub.docker.com/r/hendurhance/koel
- **Tags:** `1.0.0`, `latest` — multi-arch (`linux/amd64`, `linux/arm64`)

## Run

Point it at a running Koel API with `NUXT_KOEL_API_BASE`:

```bash
docker run -d -p 3000:3000 \
  -e NUXT_KOEL_API_BASE=http://your-koel-api:8000 \
  hendurhance/koel-frontend:1.0.0
```

Usually run as part of the full stack — see `docker-compose.prod.yml` in the repo. Listens on `:3000`.

## License

[Elastic License 2.0](https://github.com/hendurhance/koel/blob/main/LICENSE).
