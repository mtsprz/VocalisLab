-- Práctica guiada en casa / en vivo (enlace por WhatsApp).
-- Solo se guardan números (porcentaje dentro del camino, F0, estabilidad,
-- ruido del ambiente). Nunca audio.

create table if not exists practicas (
  id uuid primary key default gen_random_uuid(),
  paciente_id uuid not null references pacientes(id) on delete cascade,
  token text not null unique,
  creada_at timestamptz not null default now(),
  vence_at timestamptz not null,
  activa boolean not null default true,
  saludo text,
  indicaciones text,
  ejercicios jsonb not null default '[]'::jsonb,
  consentimiento_at timestamptz,
  consentimiento jsonb
);
create index if not exists practicas_paciente_idx on practicas (paciente_id, creada_at desc);

create table if not exists practica_sesiones (
  id uuid primary key default gen_random_uuid(),
  practica_id uuid not null references practicas(id) on delete cascade,
  paciente_id uuid not null references pacientes(id) on delete cascade,
  creada_at timestamptz not null default now(),
  modo text not null default 'casa',
  resultados jsonb not null default '[]'::jsonb,
  ambiente jsonb,
  comentario text
);
create index if not exists practica_sesiones_paciente_idx on practica_sesiones (paciente_id, creada_at desc);

-- Solo el servidor (service role) accede: sin políticas públicas.
alter table practicas enable row level security;
alter table practica_sesiones enable row level security;
