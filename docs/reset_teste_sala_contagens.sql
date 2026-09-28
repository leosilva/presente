-- Rode isso primeiro no SQL Editor do Supabase para ver o que existe
-- antes de apagar qualquer coisa. Nao apaga nada.
select 'presente_itemrecompensa' as tabela, count(*) from presente_itemrecompensa
union all select 'presente_troca', count(*) from presente_troca
union all select 'presente_pointhistory', count(*) from presente_pointhistory
union all select 'presente_attendanceremovallog', count(*) from presente_attendanceremovallog
union all select 'presente_attendance', count(*) from presente_attendance
union all select 'presente_conquistausuario', count(*) from presente_conquistausuario
union all select 'presente_brinde', count(*) from presente_brinde
union all select 'presente_activity', count(*) from presente_activity
union all select 'presente_usuariogamificacao', count(*) from presente_usuariogamificacao
union all select 'presente_gamificacao', count(*) from presente_gamificacao
union all select 'presente_tipogamificacao', count(*) from presente_tipogamificacao
union all select 'presente_trilhagamificacao', count(*) from presente_trilhagamificacao
union all select 'presente_evento', count(*) from presente_evento
union all select 'presente_perfilgamificado (com nivel)', count(*) from presente_perfilgamificado where nivel_id is not null;

-- Para conferencia: estes NAO sao tocados pelo reset.
select 'users_user (mantido)' as tabela, count(*) from users_user
union all select 'presente_nivel (mantido)', count(*) from presente_nivel
union all select 'presente_conquista (regras, mantido)', count(*) from presente_conquista
union all select 'presente_area (mantido)', count(*) from presente_area
union all select 'presente_marcosdiversidade (mantido)', count(*) from presente_marcosdiversidade;
