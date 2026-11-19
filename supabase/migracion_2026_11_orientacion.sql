-- Orientaciones clínicas guardadas (ficha integral).
create table if not exists orientaciones_clinicas (
  id uuid primary key default gen_random_uuid(),
  paciente_id uuid not null references pacientes(id) on delete cascade,
  creada_at timestamptz not null default now(),
  texto text not null,
  editado boolean not null default false,
  etapa_quirurgica text,
  situacion jsonb,
  valores_a_revisar jsonb,
  completo boolean,
  modelo text
);
create index if not exists orientaciones_paciente_idx on orientaciones_clinicas (paciente_id, creada_at desc);
alter table orientaciones_clinicas enable row level security;
