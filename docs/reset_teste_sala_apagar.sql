-- SO rode isso depois de conferir as contagens em
-- reset_teste_sala_contagens.sql e confirmar que faz sentido apagar.
--
-- Mantem: users_user (e contas SUAP), presente_nivel, presente_conquista
-- (regras), presente_area, presente_marcosdiversidade.
-- Apaga: historico de pontos/presencas/trocas + eventos/atividades/
-- trilhas antigos. Zera nivel/titulo do perfil (nao apaga o perfil).
--
-- Tudo em uma transacao: se algo falhar no meio, nada e' apagado.

begin;

delete from presente_itemrecompensa;
delete from presente_troca;
delete from presente_pointhistory;
delete from presente_attendanceremovallog;
delete from presente_attendance;
delete from presente_conquistausuario;

delete from presente_activity_owners;
delete from presente_activity_allowed_networks;

delete from presente_brinde;
delete from presente_activity;

delete from presente_usuariogamificacao;

-- Evita erro de FK caso alguma trilha tenha um "bonus" apontando pra uma
-- gamificacao que estamos prestes a apagar.
update presente_trilhagamificacao set gamificacao_bonus_id = null;

delete from presente_gamificacao;
delete from presente_tipogamificacao;
delete from presente_trilhagamificacao;

delete from presente_evento_campus;
delete from presente_evento;

update presente_perfilgamificado set nivel_id = null, titulo = null;

commit;

-- Confira depois: todas as contagens abaixo devem vir 0 (exceto perfil,
-- que so deve mostrar 0 com nivel preenchido).
select 'presente_itemrecompensa' as tabela, count(*) from presente_itemrecompensa
union all select 'presente_troca', count(*) from presente_troca
union all select 'presente_pointhistory', count(*) from presente_pointhistory
union all select 'presente_attendance', count(*) from presente_attendance
union all select 'presente_activity', count(*) from presente_activity
union all select 'presente_gamificacao', count(*) from presente_gamificacao
union all select 'presente_trilhagamificacao', count(*) from presente_trilhagamificacao
union all select 'presente_evento', count(*) from presente_evento
union all select 'presente_perfilgamificado (com nivel)', count(*) from presente_perfilgamificado where nivel_id is not null;
