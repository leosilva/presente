from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


OUTPUT_FILE = Path("docs/tarefas-gamificacao-presente.docx")


SECTIONS: list[tuple[str, list[str]]] = [
    (
        "Contexto analisado na base atual",
        [
            "A aplicacao possui autenticacao institucional via SUAP, perfis de usuario, cadastro de atividades, registro de presenca por QR Code dinamico, dashboard, pagina de perfil e relatorios de presenca em PDF/CSV.",
            "As entidades centrais para gamificacao ja existem: usuario, atividade, tags da atividade e presenca. Isso permite implantar regras de recompensa sem mudar o fluxo principal de check-in.",
            "Os pontos de entrada mais naturais para a gamificacao sao o registro de presenca, o dashboard inicial, a tela de perfil, a lista de presencas do usuario, a pagina detalhada da atividade e o painel administrativo.",
        ],
    ),
    (
        "Epic 1 - Regras e arquitetura da gamificacao",
        [
            "Card: Definir a politica de gamificacao da plataforma. Descricao: documentar objetivos, publico-alvo, comportamentos incentivados, tipos de recompensa e limites antifraude. Criterios de aceite: regras aprovadas para aluno e servidor, definicao de pontos base por presenca, eventos que nao pontuam e politica para presencas duplicadas ou invalidadas.",
            "Card: Modelar entidades de gamificacao no Django. Descricao: criar models para perfil gamificado do usuario, movimentacao de pontos, niveis, badges/conquistas e historico de desbloqueios. Criterios de aceite: migracoes criadas, relacoes com User e Attendance definidas, campos para auditoria e status ativos/inativos adicionados.",
            "Card: Criar servico central de pontuacao. Descricao: implementar camada de servico para calcular, creditar, debitar e consultar pontos sem espalhar regra em views. Criterios de aceite: API interna reutilizavel, regras isoladas por evento e cobertura de testes unitarios para calculo e idempotencia.",
            "Card: Definir estrategia de idempotencia e auditoria. Descricao: garantir que o mesmo check-in nao gere pontos duplicados e que toda concessao de recompensa fique rastreavel. Criterios de aceite: chave de origem por evento, trilha de auditoria e protecao contra dupla execucao por refresh ou concorrencia.",
        ],
    ),
    (
        "Epic 2 - Pontuacao por presenca e comportamento",
        [
            "Card: Pontuar check-in realizado com sucesso. Descricao: ao criar Attendance pela tela de check-in, conceder pontos base ao participante. Criterios de aceite: pontos creditados apenas quando a presenca for nova, mensagem de sucesso exibe a recompensa recebida e tentativas repetidas nao somam novamente.",
            "Card: Implementar bonus por sequencia de participacoes. Descricao: calcular streak de presencas em dias ou atividades consecutivas para incentivar recorrencia. Criterios de aceite: regra configuravel, persistencia da sequencia atual e da melhor sequencia, bonus aplicado somente quando a sequencia evolui.",
            "Card: Implementar bonus por diversidade de tags. Descricao: usar as tags ja existentes nas atividades para premiar usuarios que participam de temas diferentes. Criterios de aceite: contagem por tag unica, desbloqueio de bonus ao atingir marcos e consulta eficiente no historico do usuario.",
            "Card: Implementar bonus por participacao antecipada em campanha. Descricao: premiar usuarios que aderem cedo a uma atividade ou trilha definida. Criterios de aceite: janela de bonus configuravel por atividade ou regra global e registro explicito da origem do bonus.",
            "Card: Definir penalidade ou estorno administrativo. Descricao: permitir reversao de pontos quando uma presenca for removida por um responsavel. Criterios de aceite: exclusao de Attendance gera estorno coerente, historico de transacao preservado e saldo final recalculado corretamente.",
        ],
    ),
    (
        "Epic 3 - Conquistas, niveis e progressao",
        [
            "Card: Implementar sistema de niveis do usuario. Descricao: transformar pontos acumulados em nivel, titulo e progresso para o proximo marco. Criterios de aceite: niveis configuraveis, calculo automatico por faixa de pontos e exibicao do progresso percentual no perfil.",
            "Card: Criar catalogo de badges/conquistas. Descricao: permitir cadastrar conquistas como primeira presenca, cinco atividades, participacao em tres tags, streak de sete check-ins e similares. Criterios de aceite: badges com nome, descricao, icone e criterio; desbloqueio automatico por regra; suporte a badges ativas e inativas.",
            "Card: Implementar desbloqueio automatico de conquistas. Descricao: avaliar gatilhos apos novos check-ins e atualizar o historico do usuario. Criterios de aceite: sem desbloqueio duplicado, persistencia da data de conquista e testes cobrindo varios cenarios de meta.",
            "Card: Criar trilhas de engajamento por perfil. Descricao: diferenciar metas para alunos e servidores com base no campo type do User. Criterios de aceite: regras independentes por tipo de usuario, fallback para usuario sem tipo definido e exibicao correta no frontend.",
        ],
    ),
    (
        "Epic 4 - Experiencia do usuario no frontend",
        [
            "Card: Exibir recompensa no resultado do check-in. Descricao: atualizar a tela de sucesso em checkin_done para mostrar pontos ganhos, nivel atual e conquista desbloqueada. Criterios de aceite: feedback visivel apenas quando houver ganho, mensagens diferentes para primeira presenca e tentativa repetida, layout responsivo.",
            "Card: Adicionar widget de gamificacao ao dashboard. Descricao: complementar a IndexView com saldo de pontos, nivel, streak atual e ultimas conquistas. Criterios de aceite: cards novos na home, consulta eficiente, experiencia distinta para participante e responsavel.",
            "Card: Evoluir a pagina de perfil com area gamificada. Descricao: incluir progresso, badges, ranking pessoal e resumo de historico na tela profile.html. Criterios de aceite: secoes novas integradas ao perfil atual, uso de avatar existente e informacoes ordenadas por relevancia.",
            "Card: Exibir historico gamificado em minhas presencas. Descricao: adicionar indicadores de pontos obtidos e origem das recompensas na listagem do proprio usuario. Criterios de aceite: filtro ou coluna nova, sem comprometer pagina atual e com boa leitura em mobile.",
            "Card: Criar componentes visuais reutilizaveis para gamificacao. Descricao: padronizar card de badge, barra de progresso, medalhas e indicadores de ranking. Criterios de aceite: componentes reaproveitaveis em templates Django, estilo consistente com a interface existente e sem duplicacao excessiva de HTML.",
        ],
    ),
    (
        "Epic 5 - Rankings e competicao saudavel",
        [
            "Card: Criar ranking geral de participantes. Descricao: listar usuarios por pontos acumulados e quantidade de presencas confirmadas. Criterios de aceite: ordenacao previsivel, desempate definido e pagina acessivel apenas a perfis autorizados conforme regra de negocio.",
            "Card: Criar rankings segmentados por campus, curso e tipo de usuario. Descricao: aproveitar os campos campus, curso e type do User para rankings mais justos. Criterios de aceite: filtros funcionais, consultas otimizadas e ausencia de erro para usuarios com dados incompletos.",
            "Card: Exibir posicao do usuario no dashboard e no perfil. Descricao: mostrar colocacao atual, variacao recente e distancia para o proximo colocado. Criterios de aceite: calculo correto da posicao, exibicao discreta e sem expor informacoes sensiveis desnecessarias.",
            "Card: Definir limites de privacidade e moderacao do ranking. Descricao: parametrizar se o ranking sera publico, interno, anonimo ou restrito por contexto. Criterios de aceite: configuracao administrativa, ocultacao de usuarios quando necessario e alinhamento com politica institucional.",
        ],
    ),
    (
        "Epic 6 - Gamificacao para organizadores de atividades",
        [
            "Card: Recompensar criacao e conclusao de atividades relevantes. Descricao: conceder pontos ou selos para responsaveis que criam atividades, mantem a atividade habilitada e registram publico real. Criterios de aceite: pontuacao nao pode incentivar spam, regras dependem de minimo de participantes e atividades canceladas nao pontuam.",
            "Card: Criar metricas de engajamento por atividade. Descricao: mostrar na tela de detalhe da atividade indicadores como taxa de comparecimento, quantidade de participantes unicos e impacto na gamificacao. Criterios de aceite: metricas visiveis na ActivityDetailView e calculadas a partir dos dados existentes.",
            "Card: Criar conquista para curadoria de atividades por tema. Descricao: usar tags para premiar organizadores que mantem oferta variada de atividades. Criterios de aceite: criterio baseado em tags distintas e historico do organizador atualizado corretamente.",
        ],
    ),
    (
        "Epic 7 - Administracao e configuracao",
        [
            "Card: Criar painel administrativo de regras gamificadas. Descricao: disponibilizar CRUD para niveis, badges, campanhas, faixas de pontuacao e parametros de ranking. Criterios de aceite: telas protegidas para superusuario, formularios validados e navegacao consistente com o modulo administrativo atual.",
            "Card: Permitir ativacao gradual da gamificacao. Descricao: adicionar flags para habilitar modulos como pontos, badges e ranking por ambiente ou por periodo. Criterios de aceite: recurso pode ser ligado sem impacto no fluxo atual e rollback simples.",
            "Card: Registrar logs administrativos de configuracao. Descricao: auditar alteracoes em regras para facilitar suporte e governanca. Criterios de aceite: historico de quem alterou, quando alterou e quais campos mudaram.",
        ],
    ),
    (
        "Epic 8 - Relatorios, analytics e acompanhamento",
        [
            "Card: Incluir dados gamificados em relatorios exportaveis. Descricao: permitir exportar pontos, nivel, badges e ranking junto com informacoes de presenca quando fizer sentido. Criterios de aceite: colunas opcionais no PDF/CSV, sem quebrar formato atual e com nomes compreensiveis.",
            "Card: Criar dashboard administrativo de engajamento. Descricao: acompanhar usuarios ativos, media de pontos, badges mais desbloqueadas e atividades com maior adesao. Criterios de aceite: indicadores principais disponiveis para superusuario e consultas com desempenho aceitavel.",
            "Card: Monitorar impacto da gamificacao. Descricao: medir se houve aumento de presencas, recorrencia e diversidade de participacao apos ativacao do recurso. Criterios de aceite: definicao de KPIs, comparacao por periodo e visao antes/depois.",
        ],
    ),
    (
        "Epic 9 - Qualidade, seguranca e rollout",
        [
            "Card: Criar testes automatizados para regras de gamificacao. Descricao: cobrir models, services, sinais, views e templates criticos. Criterios de aceite: cenarios de primeira presenca, duplicidade, estorno, desbloqueio de badge e ranking cobertos por testes.",
            "Card: Validar desempenho das consultas de ranking e historico. Descricao: revisar indexes, agregacoes e prefetch/select_related para evitar degradacao em listas e dashboards. Criterios de aceite: endpoints principais sem N+1 relevante e tempo de resposta dentro do esperado.",
            "Card: Revisar riscos de abuso e fraude. Descricao: garantir que a gamificacao nao premie tentativas repetidas, acessos fora da regra de IP ou manipulacoes de dados. Criterios de aceite: protecoes alinhadas ao fluxo atual de check-in e cenarios de abuso documentados.",
            "Card: Planejar rollout institucional. Descricao: definir fase piloto, comunicacao para usuarios e criterio de expansao. Criterios de aceite: cronograma de implantacao, estrategia de feedback e plano de ajuste pos-lancamento.",
        ],
    ),
    (
        "Sugestao de prioridade para execucao",
        [
            "Fase 1: Epic 1, Epic 2 e o primeiro card da Epic 4. Entrega a base tecnica e o valor mais visivel no fluxo de check-in.",
            "Fase 2: Epic 3 e restante da Epic 4. Consolida progressao, badges e experiencia do usuario.",
            "Fase 3: Epic 5, Epic 6 e Epic 8. Amplia competicao saudavel, visao gerencial e valor para organizadores.",
            "Fase 4: Epic 7 e Epic 9. Fecha governanca, operacao segura e rollout controlado.",
        ],
    ),
]


def make_paragraph(text: str, *, bold: bool = False, size_half_points: int | None = None) -> str:
    text = escape(text)
    props = []
    if bold:
        props.append("<w:b/>")
    if size_half_points is not None:
        props.append(f'<w:sz w:val="{size_half_points}"/>')
        props.append(f'<w:szCs w:val="{size_half_points}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return (
        "<w:p>"
        "<w:r>"
        f"{rpr}"
        f"<w:t xml:space=\"preserve\">{text}</w:t>"
        "</w:r>"
        "</w:p>"
    )


def build_document_xml() -> str:
    body: list[str] = []
    body.append(make_paragraph("Backlog de Gamificacao - presente!", bold=True, size_half_points=32))
    body.append(make_paragraph("Documento elaborado a partir da analise do codigo fonte da aplicacao Django existente.", size_half_points=22))
    body.append(make_paragraph(""))

    for title, items in SECTIONS:
        body.append(make_paragraph(title, bold=True, size_half_points=26))
        for item in items:
            body.append(make_paragraph(item, size_half_points=22))
        body.append(make_paragraph(""))

    sect_pr = (
        "<w:sectPr>"
        '<w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>'
        "</w:sectPr>"
    )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:w10="urn:schemas-microsoft-com:office:word" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
        'xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" '
        'xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
        'mc:Ignorable="w14 wp14">'
        "<w:body>"
        f"{''.join(body)}"
        f"{sect_pr}"
        "</w:body>"
        "</w:document>"
    )


def write_docx(output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

    with ZipFile(output_file, "w", compression=ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", rels)
        docx.writestr("word/document.xml", build_document_xml())


if __name__ == "__main__":
    write_docx(OUTPUT_FILE)
    print(OUTPUT_FILE)
