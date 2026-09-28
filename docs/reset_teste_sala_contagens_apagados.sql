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
