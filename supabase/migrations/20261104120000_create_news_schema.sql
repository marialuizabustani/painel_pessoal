-- =============================================================================
-- Painel Pessoal — schema de notícias (trend forecasting, consumer insights,
-- emerging tech, fashion tech, retail innovation, coolhunting, foresight,
-- disruptive innovation, cultural trends).
--
-- Modelo:
--   sources ──< articles >──< article_topics >── topics
--   ingestion_runs  (auditoria de cada execução do pipeline)
--   articles_feed   (view consumida pelo front-end via PostgREST)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- sources: veículos / feeds monitorados
-- ---------------------------------------------------------------------------
create table if not exists public.sources (
  id          bigint generated always as identity primary key,
  slug        text        not null unique,
  name        text        not null,
  site_url    text        not null,
  feed_url    text        not null unique,
  language    text        not null check (language in ('en', 'pt')),
  kind        text        not null default 'rss' check (kind in ('rss', 'google_news')),
  is_curated  boolean     not null default false, -- fonte 100% on-topic (dispensa filtro)
  is_active   boolean     not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create trigger trg_sources_updated_at
before update on public.sources
for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- topics: taxonomia de temas (bilíngue)
-- ---------------------------------------------------------------------------
create table if not exists public.topics (
  id       smallint generated always as identity primary key,
  slug     text not null unique,
  name_en  text not null,
  name_pt  text not null
);

insert into public.topics (slug, name_en, name_pt) values
  ('trend-forecasting',     'Trend Forecasting',     'Previsão de Tendências'),
  ('consumer-insights',     'Consumer Trends',       'Tendências de Consumo'),
  ('emerging-tech',         'Emerging Technologies', 'Tecnologias Emergentes'),
  ('fashion-tech',          'Fashion Tech',          'Moda & Tecnologia'),
  ('retail-innovation',     'Retail Innovation',     'Inovação no Varejo'),
  ('coolhunting',           'Coolhunting',           'Coolhunting'),
  ('foresight',             'Foresight',             'Foresight'),
  ('disruptive-innovation', 'Disruptive Innovation', 'Inovação Disruptiva'),
  ('cultural-trends',       'Cultural Trends',       'Tendências Culturais')
on conflict (slug) do nothing;

-- ---------------------------------------------------------------------------
-- articles: manchetes coletadas
-- ---------------------------------------------------------------------------
create table if not exists public.articles (
  id               bigint generated always as identity primary key,
  source_id        bigint       not null references public.sources (id) on delete cascade,
  url              text         not null unique,
  title            text         not null,
  summary          text,
  image_url        text,
  author           text,
  publisher        text,        -- veículo original (ex.: agregadores como Google News)
  language         text         not null check (language in ('en', 'pt')),
  published_at     timestamptz,
  collected_at     timestamptz  not null default now(),
  collected_on     date         not null default ((now() at time zone 'America/Sao_Paulo')::date),
  relevance_score  numeric(6,2) not null default 0,
  created_at       timestamptz  not null default now(),
  updated_at       timestamptz  not null default now(),
  constraint articles_url_http check (url ~* '^https?://')
);

create index if not exists idx_articles_published_at on public.articles (published_at desc nulls last);
create index if not exists idx_articles_collected_on on public.articles (collected_on desc);
create index if not exists idx_articles_language     on public.articles (language);
create index if not exists idx_articles_source_id    on public.articles (source_id);

create trigger trg_articles_updated_at
before update on public.articles
for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- article_topics: N:N artigos x temas
-- ---------------------------------------------------------------------------
create table if not exists public.article_topics (
  article_id  bigint       not null references public.articles (id) on delete cascade,
  topic_id    smallint     not null references public.topics (id)   on delete cascade,
  score       numeric(6,2) not null default 0,
  primary key (article_id, topic_id)
);

create index if not exists idx_article_topics_topic_id on public.article_topics (topic_id);

-- ---------------------------------------------------------------------------
-- ingestion_runs: observabilidade do pipeline
-- ---------------------------------------------------------------------------
create table if not exists public.ingestion_runs (
  id                 bigint generated always as identity primary key,
  started_at         timestamptz not null default now(),
  finished_at        timestamptz,
  status             text        not null default 'running'
                     check (status in ('running', 'success', 'partial', 'failed')),
  feeds_total        integer     not null default 0,
  feeds_failed       integer     not null default 0,
  articles_seen      integer     not null default 0,
  articles_inserted  integer     not null default 0,
  articles_updated   integer     not null default 0,
  errors             jsonb       not null default '[]'::jsonb,
  run_url            text
);

-- ---------------------------------------------------------------------------
-- View pública para o front-end
-- ---------------------------------------------------------------------------
create or replace view public.articles_feed
with (security_invoker = true)
as
select
  a.id,
  a.title,
  a.summary,
  a.url,
  a.image_url,
  a.language,
  a.published_at,
  a.collected_on,
  a.relevance_score,
  coalesce(a.publisher, s.name)                             as source_name,
  s.site_url                                                as source_url,
  coalesce(array_agg(t.slug order by at.score desc)
           filter (where t.slug is not null), '{}')         as topics
from public.articles a
join public.sources s          on s.id = a.source_id
left join public.article_topics at on at.article_id = a.id
left join public.topics t      on t.id = at.topic_id
group by a.id, s.id;

-- ---------------------------------------------------------------------------
-- Row Level Security
--   anon/authenticated: somente leitura do conteúdo público
--   ingestion_runs: sem acesso pela API (apenas o pipeline, via conexão direta)
-- ---------------------------------------------------------------------------
alter table public.sources        enable row level security;
alter table public.topics         enable row level security;
alter table public.articles       enable row level security;
alter table public.article_topics enable row level security;
alter table public.ingestion_runs enable row level security;

create policy "public read sources"        on public.sources        for select to anon, authenticated using (is_active);
create policy "public read topics"         on public.topics         for select to anon, authenticated using (true);
create policy "public read articles"       on public.articles       for select to anon, authenticated using (true);
create policy "public read article_topics" on public.article_topics for select to anon, authenticated using (true);

revoke all on public.ingestion_runs from anon, authenticated;
revoke insert, update, delete, truncate on
  public.sources, public.topics, public.articles, public.article_topics
from anon, authenticated;
grant select on public.articles_feed to anon, authenticated;
