-- Google OAuth Credentials
create table if not exists google_auth (
  user_id text primary key,
  access_token text not null,
  refresh_token text not null,
  sync_token text,
  expires_at timestamp with time zone,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

alter table google_auth enable row level security;
create policy "Enable all access for all users" on google_auth for all using (true) with check (true);

-- Google Calendar Event Mappings
create table if not exists calendar_event_mappings (
  id uuid primary key default gen_random_uuid(),
  google_event_id text not null unique,
  patient_id text references patients(id) on delete cascade,
  session_id text references appointments(id) on delete set null,
  sync_status text check (sync_status in ('mapped', 'pending')) default 'pending',
  last_synced_at timestamp with time zone default timezone('utc'::text, now()),
  created_at timestamp with time zone default timezone('utc'::text, now())
);

alter table calendar_event_mappings enable row level security;
create policy "Enable all access for all users" on calendar_event_mappings for all using (true) with check (true);
