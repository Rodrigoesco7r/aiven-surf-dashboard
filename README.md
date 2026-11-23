# 🏄 Dashboard de Surf — Ondas do Brasil

Dashboard em tempo real com as condições de surf nos principais spots do Brasil.

**Stack:** Python/Flask · PostgreSQL (Aiven) · Docker · GitHub Actions · Render.com

## Funcionalidades

- Ranking dos melhores spots de surf do Brasil por score
- Gráfico de altura de ondas por spot
- Dados de período, vento e temperatura da água
- Contador de visitas persistido no banco
- Pipeline CI/CD completo: test → build → deploy

## Spots monitorados

Fernando de Noronha (PE), Itamambuca (SP), Maresias (SP), Saquarema (RJ),
Arpoador (RJ), Joaquina (SC), Campeche (SC), Torres (RS),
Porto de Galinhas (PE), Jericoacoara (CE), Canoa Quebrada (CE),
Itacaré (BA), Praia do Forte (BA), Barra da Tijuca (RJ), Geribá (RJ)

## Arquitetura

```
GitHub Actions
  ├── infra.yml       → Terraform provisiona PostgreSQL na Aiven
  └── ci-cd.yml       → test → build Docker → push GHCR → deploy Render
```

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `AIVEN_DB_URL` | URI de conexão do PostgreSQL da Aiven |
| `PORT` | Porta HTTP (default: 8080) |
| `CACHE_HOURS` | Horas entre atualizações da API (default: 3) |

## Secrets do GitHub

| Secret | Valor |
|---|---|
| `AIVEN_API_TOKEN` | Token de API da Aiven |
| `AIVEN_PROJECT` | Nome do projeto na Aiven |
| `RENDER_DEPLOY_HOOK_URL` | Deploy Hook do Render |
| `APP_HEALTHCHECK_URL` | URL pública do app no Render |

## Fonte de dados

[Open-Meteo Marine API](https://open-meteo.com/en/docs/marine-weather-api) — gratuita, sem chave de API.
