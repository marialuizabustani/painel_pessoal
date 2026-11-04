# Painel Pessoal: Radar de Tendências

Um painel diário de manchetes sobre **trend forecasting, consumer trends e insights, tecnologias emergentes, fashion tech, inovação no varejo, coolhunting, foresight, inovação disruptiva e tendências culturais**, em **português e inglês**.

```
GitHub Actions (cron 06:00 BRT)            Supabase (Postgres)             GitHub Pages
┌──────────────────────────────┐   SQL    ┌────────────────────┐  REST   ┌──────────────┐
│ collector/ (Python)          │ ───────▶ │ sources            │ ◀────── │ web/index.html│
│  RSS editoriais + Google News│          │ articles ─┐        │  (RLS,  │ supabase-js  │
│  classificação bilíngue      │          │ article_topics ─ topics      │  read-only)  │
│  upsert idempotente          │          │ ingestion_runs     │         └──────────────┘
└──────────────────────────────┘          │ view articles_feed │
                                          └────────────────────┘
```

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `supabase/migrations/` | Modelagem de dados (tabelas, índices, view, RLS) |
| `collector/` | Pipeline de coleta (Python 3.11+): fontes, parsing, classificação e persistência |
| `web/index.html` | Página estática publicada no GitHub Pages |
| `.github/workflows/collect-news.yml` | Coleta diária às 06:00 de Brasília (09:00 UTC), mais disparo manual |
| `.github/workflows/deploy-pages.yml` | Publica `web/` no GitHub Pages a cada push na `main` |
| `.github/workflows/ci.yml` | Lint (ruff) e testes (pytest) do coletor |

## Modelo de dados

- **sources**: veículos/feeds monitorados (`language`: `en`/`pt`, `kind`: `rss`/`google_news`, `is_curated`).
- **topics**: taxonomia bilíngue com 9 temas.
- **articles**: manchetes com URL única (sem parâmetros `utm_*`), resumo, imagem, veículo, `published_at`, `collected_on` (data em America/Sao_Paulo) e `relevance_score`.
- **article_topics**: relação N:N entre artigo e tema, com pontuação.
- **ingestion_runs**: auditoria de cada execução (status, contagens, erros, link do run). Não é exposta pela API.
- **articles_feed**: view (`security_invoker`) que o front-end consome.

RLS: `anon`/`authenticated` têm **somente leitura** em `sources`, `topics`, `articles` e `article_topics`. A escrita acontece apenas pela conexão Postgres do pipeline.

## Como o coletor funciona

1. Lê ~28 feeds RSS editoriais (Springwise, Trend Hunter, PSFK, BoF, Vogue Business, Glossy, Modern Retail, MIT Tech Review, Mercado & Consumo, Consumidor Moderno, StartSe, B9, Meio & Mensagem, FFW, FashionNetwork BR…) e 18 buscas temáticas no Google News (9 temas × EN/PT, janela de 1 dia).
2. Normaliza URLs, limpa o HTML do resumo, extrai imagem e data.
3. Classifica por tema com um léxico bilíngue com pesos (o título vale o dobro do resumo). Fontes curadas e buscas temáticas sempre entram; nas demais, só entram matérias com pontuação ≥ 2.
4. Faz upsert idempotente (`on conflict (url)`), com uma transação por fonte. Se uma fonte falhar, as outras seguem normalmente.

Para adicionar ou remover fontes, edite `collector/src/collector/sources.py`. Para ajustar a classificação, edite `collector/src/collector/classifier.py`.

## Configuração (uma vez)

1. **Secret do banco**: em *Settings → Secrets and variables → Actions → New repository secret*, crie `SUPABASE_DB_URL` com a connection string Postgres do Supabase (pooler, porta 6543). **Nunca commite essa string.**
2. **GitHub Pages**: em *Settings → Pages → Build and deployment → Source*, escolha **GitHub Actions**. Depois rode o workflow *Deploy GitHub Pages* (ou faça um push em `web/`).
3. **Migração**: aplique `supabase/migrations/*.sql` pelo SQL Editor do Supabase ou com `supabase db push`. Já foi aplicada no projeto atual.
4. Para a primeira carga, rode *Actions → Collect daily news → Run workflow*.

## Desenvolvimento local

```bash
cd collector
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check . && pytest
DRY_RUN=1 trend-collector                       # coleta sem gravar
SUPABASE_DB_URL='postgresql://…' trend-collector   # coleta e grava
```

> O agendamento do GitHub Actions usa UTC e pode atrasar alguns minutos em horários de pico.
