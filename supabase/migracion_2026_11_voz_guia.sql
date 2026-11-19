-- Voz guía del profesional (frases e indicaciones grabadas con su voz).
create table if not exists voz_guia (
  clave text primary key,
  mime text not null default 'audio/wav',
  audio_b64 text not null,
  duracion_s float,
  actualizada_at timestamptz not null default now()
);
alter table voz_guia enable row level security;
