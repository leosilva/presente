# Plano: privacidade no ranking, ranking por evento, responsividade mobile e bug de login SUAP

> Planejamento da branch `ux-aluno-gamificacao`. Itens 1-3 abaixo ainda estão pendentes nesta branch. O item 4 (SUAP) já foi corrigido e isolado na branch `fix-suap-https-proxy` (commit `f7513e3`, enviado ao `origin`).

## Contexto

O usuário levantou 4 pontos depois de testar o app no celular:
1. A foto do usuário no ranking expõe dado pessoal desnecessário — só o nome deveria aparecer.
2. O "Ranking Geral" deveria ser por Evento (cada evento tem sua própria competição de pontos).
3. Existem quebras de layout em telas de celular menores (~360-375px) em algumas páginas.
4. ~~Depois do login com SUAP, em alguns iPhones aparece um formulário pedindo email e, ao enviar, um erro de "login de terceiros".~~ **Corrigido** — ver branch `fix-suap-https-proxy`.

Investigação (3 agentes de exploração) confirmou que os itens 2 e 4 não eram ajustes triviais:
- `PointHistory` (onde os pontos são creditados/debitados) não tem nenhum vínculo com `Evento` hoje — só `Activity` tem. Pra "ranking por evento" funcionar de verdade, é preciso adicionar esse vínculo.
- O bug do SUAP no iPhone tinha uma causa raiz concreta e confirmada: o Render entrega HTTP puro pro container (TLS é terminado no proxy do Render), e o Django não tinha `SECURE_PROXY_SSL_HEADER` configurado, então não sabia que estava atrás de HTTPS. Isso fazia o Django montar a `redirect_uri` do OAuth como `http://...`, enquanto o SUAP tem cadastrado (confirmado pelo usuário) `https://presente-ysqa.onrender.com/accounts/suap/login/callback/`. Corrigido adicionando `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` em produção, mais logging no erro de autenticação social.

---

## 1. Remover foto do usuário no ranking (privacidade) — PENDENTE

**Arquivo:** `templates/presente/ranking.html`

- Remover o bloco `<img class="rank-avatar" ...>` (dentro de cada `.rank-row`, entre o indicador de posição/medalha e o `.rank-info`).
- Manter medalha/posição, nome (+ badge "Você"), campus/curso e pontos — só tira a imagem.

**Arquivo:** `static/css/presente.css`

- Remover a classe `.rank-avatar` (fica órfã depois da remoção acima).

Baixo risco, sem efeito colateral em outras páginas (essa é a única lista de ranking do app).

---

## 2. "Ranking Geral" → "Ranking do Evento" — PENDENTE

### 2.1 Modelo — adicionar `evento` em `PointHistory`

**Arquivo:** `presente/models.py` (classe `PointHistory`)

Adicionar:
```python
evento = models.ForeignKey(
    "Evento",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="point_history",
    verbose_name=_("Evento"),
    help_text=_("Evento ao qual este crédito/débito está vinculado, quando aplicável."),
)
```
Gerar migração (`makemigrations`). Incluir uma migração de dados (`RunPython`) que tenta preencher `evento` nos registros existentes cujo `gamificacao` está ligado a exatamente um evento via `Activity` (`gamificacao.activities.values_list('evento', flat=True).distinct()` tem um único valor) — o resto fica `null` (pontos "gerais"/bônus de boas-vindas não pertencem a nenhum evento mesmo).

### 2.2 Popular `evento` em todo lugar que cria `PointHistory`

**Arquivo:** `presente/services.py` — mapeamento de todos os pontos de criação:

- `PointService.credit_gamificacao` / `debit_gamificacao` (linhas 30-65): adicionar parâmetro opcional `evento=None` e incluir no `PointHistory.objects.create(...)`.
- `_on_attendance_created` (linha 101-135): passar `evento=attendance.activity.evento` pro crédito direto da gamificação da atividade (linha 112-115), pro crédito de conquista (linha 121-126, mesmo evento já usado no `ConquistaUsuario` da linha 119), e propagar `evento` pra frente em `_check_trilha_bonus(user, trilha, evento=...)` (linha 129-130) e `_check_diversidade_bonus(user, data, evento=...)` (linha 132-135).
- `_on_attendance_canceled` (linha 137-162): já tem `activity = attendance.activity` disponível — propagar `evento=activity.evento` pro `debit_gamificacao` (linha 155-156) e pros métodos de reversão de trilha/diversidade (linhas 158-162), que também precisam ganhar o parâmetro `evento=None` e repassá-lo.
- `_on_gamificacao_updated` (linha 164-171): para cada `atividade` no loop, usar `evento=atividade.evento` no débito/recrédito.
- `_check_trilha_bonus` / `_check_trilha_bonus_reversal` (linha 177-214) e `_check_diversidade_bonus` / `_check_diversidade_bonus_reversal` (linha 220-277): ganham parâmetro `evento=None`, repassado ao `credit_gamificacao`/`debit_gamificacao`.
- `TrocaService._debitar_pontos` (linha 446-464): `Brinde` já tem `evento` (visto em `get_brindes_disponiveis`, linha 482-497) — usar `evento=troca.itens.first().brinde.evento` (melhor esforço; na prática todos os itens de uma troca vêm do mesmo evento, já que a loja é escopada por evento).
- `_on_user_created` (Boas-vindas, linha 90-99): **não** propagar evento — é um bônus de boas-vindas do sistema, não pertence a nenhum evento. Fica `null` corretamente.

### 2.3 View e URL

**Arquivo:** `presente/urls.py`

Seguir o padrão já usado em `eventos/<int:evento_pk>/atividades/` (linha ~56-60): adicionar `path("eventos/<int:evento_pk>/ranking/", views.RankingListView.as_view(), name="ranking")`. **Manter** a rota antiga `path("ranking/", views.RankingListView.as_view(), name="ranking")` também funcionando (mesma view, sem `evento_pk` no kwargs) — nenhum link existente quebra, e o menu lateral não precisa ser alterado.

**Arquivo:** `presente/views.py` — `RankingListView` (linha 343-372)

- Adicionar `get_evento()`: se houver `evento_pk` na URL, `get_object_or_404(Evento, pk=...)`; senão, `Evento.objects.order_by("-data_inicio").first()` (mesmo padrão simples já usado em `LojaView`, linha ~863-870 — evento padrão = mais recente por data de início).
- `get_queryset()`: anotar `total_pontos` filtrando a soma por `point_history__evento=evento` (usando `Sum("point_history__pontos", filter=Q(point_history__evento=evento))`) quando houver evento; mantém fallback pro comportamento atual se não houver nenhum evento cadastrado.
- `get_context_data()`: adicionar `evento` (selecionado) e `eventos` (lista pra popular o seletor) ao contexto, mantendo a lógica existente de `minha_posicao`/`meus_pontos_ranking`.

### 2.4 Template

**Arquivo:** `templates/presente/ranking.html`

- Trocar o texto do cabeçalho de "Ranking Geral" para algo como `Ranking — {{ evento.nome|default:"Geral" }}`.
- Adicionar um seletor simples de evento acima da lista (um `<select class="form-select">` com `onchange="window.location.href=this.value"`, populado a partir de `eventos`, cada `<option value="{% url 'presente:ranking' evento.pk %}">`) — sem necessidade de Tom Select, é uma lista curta.

---

## 3. Responsividade mobile — PENDENTE

Achados confirmados por leitura de código (agente de exploração), por prioridade:

**P1 — risco real de estouro horizontal:**
- `templates/presente/profile.html` (`.detail-value`, no `<style>` do topo do arquivo, e usado nos campos de Email/Usuário/Matrícula/Campus/Curso em `col-6`, por volta das linhas 379-420): adicionar `overflow-wrap: break-word; word-break: break-word;` — hoje um email/username longo sem espaços pode forçar a coluna a estourar em telas de 360-375px (diferente do `.rank-meta` do ranking, que já trata isso certo com `min-width:0` + ellipsis).
- `templates/presente/public_activity.html` (linhas 29-42, caixas "Início"/"Término" com `min-width: 140px`): a folga em telas de 360px é de só ~8px — reduzir `min-width` (ex: 120px) ou adicionar uma media query que empilha as duas caixas verticalmente abaixo de ~380px.

**P2 — apertado, mas sem estourar (some cards ficam mal comprimidos em `col-6` a 360px):**
- Padrão de "stat card" (ícone 3rem + label + valor) repetido em `ranking.html`, `index.html`, `minhas_pontuacoes.html`, `minhas_recompensas.html`: adicionar uma media query em `presente.css` (`@media (max-width: 400px)`) reduzindo o ícone (3rem → ~2rem) e garantindo que o bloco de texto não force overflow.
- `templates/presente/profile.html` (nav-tabs "Meu Perfil"/"Minhas Conquistas", linha ~343): pode quebrar em duas linhas em telas muito estreitas — ajuste leve de padding/font-size via media query pra não ficar com aparência quebrada quando isso acontece.

**P4 — inconsistência de breakpoint (não quebra, mas destoa do resto do app):**
- `templates/presente/loja.html`: os cards de resumo usam `col-md-4` (linhas ~17,32,45) e os cards de brinde usam `col-md-6` (linha ~79), diferente do padrão `col-lg-3 col-6` / `col-6` usado em todas as outras páginas do app. Ajustar pra ficar consistente (2 colunas já em telas médias/phablets, igual ao resto do site).

Fora do escopo por ora (mencionado pelo agente, mas é só código morto sem efeito visual): classe `dropdown-menu-md` inválida e `w-75` neutralizado no menu do usuário (`private_base.html`) — não causam bug, só sujeira; limpar só se for pedido.

**Verificação:** não dá pra testar em celular real remotamente — validar simulando larguras estreitas (360px/375px) via inspeção do CSS resultante, e pedir confirmação do usuário no celular dele depois do deploy.

---

## 4. Bug de login SUAP no iPhone — CONCLUÍDO (branch `fix-suap-https-proxy`)

**Arquivo:** `config/settings.py`, no bloco `else` (produção, `BUILD_ENV != "local"`):

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

Faz o Django reconhecer corretamente que a requisição chegou via HTTPS (o Render entrega HTTP puro pro container atrás do proxy), corrigindo a `redirect_uri` gerada pro OAuth do SUAP e garantindo que os cookies de sessão/CSRF saiam com a flag `Secure`.

**Logging:** `users/adapters.py`, `SuapSocialAccountAdapter.on_authentication_error` loga a exceção via `logging` antes de deixar o allauth mostrar a tela padrão de erro.

**Pendente de verificação real:** validação final depende de teste em iPhone real após deploy no Render (não reproduzível localmente, sem HTTPS/proxy configurado em dev).

---

## Verificação geral (itens 1-3, ainda pendentes)

- **Item 1:** conferir visualmente a página de ranking (local), sem foto, layout limpo.
- **Item 2:** criar/usar 2 eventos com pontuações distintas localmente, acessar `/eventos/<pk>/ranking/` pra cada um e conferir que os totais batem só com pontos daquele evento; conferir que `/ranking/` (sem evento_pk) continua funcionando.
- **Item 3:** revisão de CSS simulando larguras de 360/375px; pedir confirmação do usuário no celular real após deploy.
