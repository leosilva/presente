-- Cria o evento, trilhas, areas, gamificacoes e atividades do piloto
-- (INFO 2 Vespertino, 29/09 a 02/10/2026). Rode reset_teste_sala_apagar.sql
-- antes se ainda nao rodou (precisa estar tudo zerado: nao ha protecao
-- contra duplicar o evento aqui, ao contrario do management command).
--
-- Tudo em uma transacao: se algo falhar no meio, nada e' criado.

begin;

with ev as (
  insert into presente_evento (nome, tipo, data_inicio, data_fim, descricao)
  values (
    'Aulas - INFO 2 Vespertino (piloto)',
    'OUT',
    '2026-09-29 00:00:00-03',
    '2026-10-02 23:59:00-03',
    'Piloto de gamificacao com a turma de Informatica 2o ano vespertino.'
  )
  returning id
),
trilhas_in (name) as (
  values
    ('Exatas'),
    ('Propedeuticas/Tecnicas'),
    ('Humanas'),
    ('Programacao'),
    ('Geral')
),
trilhas as (
  insert into presente_trilhagamificacao (name, descricao, minimo_atividades)
  select name, '', 1 from trilhas_in
  returning id, name
),
tipos as (
  insert into presente_tipogamificacao (trilha_id, tipo, descricao)
  select id, 'BDG', '' from trilhas
  returning id, trilha_id
),
areas_in (nome) as (
  values ('Exatas'), ('Propedeuticas/Tecnicas'), ('Humanas'), ('Programacao')
),
areas as (
  insert into presente_area (nome, descricao)
  select nome, '' from areas_in
  returning id, nome
),
-- Horario de INFO 2 Vespertino; terca-feira ja corrigida (Ingles e Arte
-- estavam trocados no horario original). Educacao Fisica usa a trilha
-- "Geral" (nao se encaixa nas 4 tematicas) e fica sem Area.
aulas (dia, hora_ini, hora_fim, materia, professor, trilha_nome) as (
  values
    ('2026-09-29'::date, '13:00'::time, '14:30'::time, 'Ingles I', 'Tito Matias', 'Humanas'),
    ('2026-09-29'::date, '14:50'::time, '16:20'::time, 'Arte III', 'Cristina Tapuya', 'Humanas'),
    ('2026-09-29'::date, '16:30'::time, '18:00'::time, 'Matematica II', 'Suzany Medeiros', 'Exatas'),
    ('2026-09-30'::date, '13:00'::time, '14:30'::time, 'Filosofia II', 'Stanley Kreiter', 'Humanas'),
    ('2026-09-30'::date, '14:50'::time, '16:20'::time, 'Redes de Computadores', 'Diogo Cortez', 'Propedeuticas/Tecnicas'),
    ('2026-09-30'::date, '16:30'::time, '18:00'::time, 'Organizacao e Montagem de Computadores', 'Lennedy Soares', 'Propedeuticas/Tecnicas'),
    ('2026-10-01'::date, '13:00'::time, '14:30'::time, 'Eletronica', 'Thales Ramos', 'Propedeuticas/Tecnicas'),
    ('2026-10-01'::date, '14:50'::time, '16:20'::time, 'Projeto de Banco de Dados', 'Keylly Santos', 'Programacao'),
    ('2026-10-01'::date, '16:30'::time, '18:00'::time, 'Organizacao e Montagem de Computadores', 'Lennedy Soares', 'Propedeuticas/Tecnicas'),
    ('2026-10-02'::date, '13:00'::time, '14:30'::time, 'Projeto de Banco de Dados', 'Keylly Santos', 'Programacao'),
    ('2026-10-02'::date, '14:50'::time, '16:20'::time, 'Matematica II', 'Suzany Medeiros', 'Exatas'),
    ('2026-10-02'::date, '16:30'::time, '18:00'::time, 'Educacao Fisica II', 'Monica Lima', 'Geral')
),
gamificacoes as (
  insert into presente_gamificacao (titulo, tipo_id, trilha_id, pontos)
  select
    'Presenca - ' || aulas.materia || ' (' || to_char(aulas.dia, 'DD/MM') || ')',
    tipos.id,
    trilhas.id,
    10
  from aulas
  join trilhas on trilhas.name = aulas.trilha_nome
  join tipos on tipos.trilha_id = trilhas.id
  returning id, trilha_id, titulo
),
activities as (
  insert into presente_activity (
    title, start_time, end_time, is_enabled, qr_timeout, restrict_ip,
    trilha_id, gamificacao_id, evento_id, area_id, created_at, modified_at
  )
  select
    aulas.materia || ' - ' || aulas.professor || ' (' || to_char(aulas.dia, 'DD/MM') || ', ' ||
      to_char(aulas.hora_ini, 'HH24:MI') || '-' || to_char(aulas.hora_fim, 'HH24:MI') || ')',
    (aulas.dia + aulas.hora_ini) at time zone 'America/Recife',
    (aulas.dia + aulas.hora_fim) at time zone 'America/Recife',
    true,
    60,
    false,
    trilhas.id,
    gamificacoes.id,
    (select id from ev),
    areas.id,
    now(),
    now()
  from aulas
  join trilhas on trilhas.name = aulas.trilha_nome
  join gamificacoes on gamificacoes.trilha_id = trilhas.id
    and gamificacoes.titulo = 'Presenca - ' || aulas.materia || ' (' || to_char(aulas.dia, 'DD/MM') || ')'
  left join areas on areas.nome = aulas.trilha_nome
  returning id
)
select
  (select count(*) from ev) as eventos_criados,
  (select count(*) from trilhas) as trilhas_criadas,
  (select count(*) from tipos) as tipos_criados,
  (select count(*) from areas) as areas_criadas,
  (select count(*) from gamificacoes) as gamificacoes_criadas,
  (select count(*) from activities) as atividades_criadas;

commit;
