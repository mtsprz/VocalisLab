-- Práctica guiada v2: veces por día indicadas y rango de trabajo de la rutina.
-- (Sin esta migración la práctica funciona igual: el rango viaja en cada ejercicio
-- y se asumen 2 prácticas por día.)
alter table practicas add column if not exists veces_por_dia int not null default 2;
alter table practicas add column if not exists rango jsonb;
