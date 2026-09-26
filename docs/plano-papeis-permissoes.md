# Papéis e permissões de cadastro (atividades, trilhas, gamificação)

## Contexto

Hoje a hierarquia é implícita e confusa:

| Quem | Como é definido | O que cadastra hoje |
|---|---|---|
| Superusuário (devs/TI) | `is_superuser` | Tudo. Eventos/Redes/Usuários por telas; **Trilhas, Gamificações, Conquistas, Níveis, Brindes, Áreas, Marcos só pelo Django admin** |
| Servidor | `type=SERVIDOR` do SUAP (`users/adapters.py`) → grupo "Servidor" com todas as permissões de `Activity` (`users/signals.py`) | As próprias atividades, com pontos livres, em qualquer evento, usando qualquer trilha |
| Aluno | `type=ALUNO` | Nada |
| `is_staff` | flag manual | Vê o menu ADMINISTRAÇÃO (`presente/menus.py`), mas as telas exigem superusuário → 403 |

Problemas: só desenvolvedores conseguem criar trilhas/brindes/conquistas; ninguém "é dono" de um evento; pontos sem limite; aluno não pode propor atividade; "Minhas Atividades" (`ActivityListView`) lista **todas** as atividades habilitadas, não só as do usuário.

Decisões do usuário:
- **Aluno propõe atividade → organizador do evento aprova** (ajustando pontos).
- **Organizadores do evento** (servidores designados) gerenciam trilhas, brindes e aprovações daquele evento, por telas próprias.
- **Teto de pontos por evento**; organizador/admin pode ultrapassar.
- **Administradores** criam eventos, designam organizadores e cuidam das regras globais (níveis, conquistas, áreas, bônus de diversidade) por telas próprias.

## Hierarquia proposta

```
Administrador (superuser / TI)
 ├─ Eventos (cria, define organizadores e teto de pontos)
 ├─ Regras globais: Níveis, Conquistas, Áreas, Bônus de diversidade, Redes, Usuários
 └─ Tudo que o organizador faz, em qualquer evento

Organizador do evento (servidor designado no evento)
 ├─ Trilhas do evento (com pontos de bônus)
 ├─ Loja/brindes do evento
 ├─ Aprovar/recusar propostas de atividade de alunos
 └─ Ver/editar todas as atividades do evento; pode passar do teto de pontos

Servidor
 ├─ Cria atividades (aprovadas direto), pontos até o teto do evento
 ├─ Usa trilhas existentes do evento (não cria)
 └─ Adiciona co-responsáveis (inclusive alunos como monitores)

Aluno
 ├─ Participa (presença, trilhas, loja)
 └─ Propõe atividade → fica "Pendente" até aprovação; pode ser co-responsável
```

## Implementação

### 1. Modelo de dados (`presente/models.py` + migration 0040)
- `Evento`: `organizadores = M2M(User, blank=True, related_name="eventos_organizados")`, `teto_pontos_atividade = PositiveIntegerField(default=50)`.
- `Activity`: `situacao` (choices `PENDENTE`/`APROVADA`/`RECUSADA`, default `APROVADA`), `motivo_recusa` (TextField blank), `proposta_por` (FK User null, SET_NULL).
  - `Activity.status` passa a retornar `"not_enabled"` quando `situacao != APROVADA` → check-in e QR bloqueados sem mexer em `CheckInView`.
  - Trilhas (`TrilhaService.caminho` em `presente/services.py`) e listagens públicas filtram `situacao=APROVADA`.
- Migration de dados: atividades existentes ficam `APROVADA`; eventos sem organizador (admin designa depois).

### 2. Regras de permissão centralizadas (novo `presente/permissions.py`)
Funções puras reutilizadas por views, forms, menus e templates:
- `eh_admin(user)` → `user.is_superuser`
- `organiza(user, evento)` / `eventos_organizados(user)`
- `pode_criar_atividade(user)` → servidor, organizador ou admin (aluno usa o fluxo de proposta)
- `pode_gerenciar_atividade(user, atividade)` → dono, organizador do evento ou admin (substitui a lógica de `ActivityOwnerMixin` em `presente/mixins.py` e os `if is_superuser` espalhados em `presente/views.py`)
- `pode_passar_teto(user, evento)` → organizador ou admin
- Context processor (`presente/context_processors.py`) expõe `eh_organizador` e `propostas_pendentes` (contagem) para menu/dashboard.

### 3. Atividades (`presente/forms.py`, `presente/views.py`)
- `ActivityForm` recebe `user` no `__init__`:
  - `evento`: servidor vê eventos em andamento/futuros; organizador/admin vê os seus/todos.
  - `pontos`: `clean_pontos` valida `<= evento.teto_pontos_atividade` salvo `pode_passar_teto`; a caixa "O participante vai ver" e o `activity_form.js` mostram o teto (`data-teto` no option do evento, mesmo padrão do `TrilhaSelect`).
- `ActivityListView` ("Minhas Atividades"): filtra `owners=user` (corrige o bug) e mostra badge de situação.
- **Proposta de aluno**: `PropostaAtividadeCreateView` (reusa `ActivityForm` em modo reduzido: sem QR/IP/redes/owners; pontos = "sugestão"). Salva `situacao=PENDENTE`, `proposta_por=user`, `is_enabled=False`, `owners=[user]`. Página "Minhas propostas" com situação e motivo de recusa.

### 4. Área do organizador (novas telas, padrão `CoreListView/CoreCreateView` de `core/views.py`, como o CRUD de Redes/Eventos)
- **Meus eventos** (`/organizacao/`): cards por evento com contadores (atividades, pendentes, trilhas, brindes).
- **Aprovações** (`/organizacao/<evento>/propostas/`): lista pendentes; aprovar (com campo de pontos, cria a gamificação via `ActivityForm._sincronizar_gamificacao`) ou recusar (com motivo).
- **Trilhas do evento**: CRUD com `TrilhaForm` (nome, descrição, mínimo de atividades, **pontos de bônus** → cria/atualiza `gamificacao_bonus` automaticamente, mesmo padrão de `_sincronizar_gamificacao`). `evento` fixo no evento organizado.
- **Brindes do evento**: CRUD de `Brinde` com `evento` fixo.
- Todas protegidas por um mixin `OrganizadorDoEventoMixin` (usa `permissions.organiza`).

### 5. Área do administrador
- `EventoForm` ganha `organizadores` (Tom Select de servidores, `data-tom-select="users"`) e `teto_pontos_atividade`.
- CRUDs de regras globais (mesmo padrão CoreViews + `tables.py`): **Níveis, Conquistas, Áreas, Bônus de diversidade** (este último com campo "pontos" que sincroniza `gamificacao_bonus`), e **Trilhas gerais** (sem evento).
- Django admin permanece só para suporte técnico.

### 6. Menu e navegação (`presente/menus.py`)
- ADMINISTRAÇÃO: condição passa a `is_superuser` (remove a inconsistência com `is_staff`).
- Nova seção **ORGANIZAÇÃO** (visível se `eventos_organizados` não vazio): Meus eventos, Aprovações (com contagem de pendentes).
- Aluno: "Propor atividade" e "Minhas propostas". Servidor: "Minhas Atividades" (já existe).
- Página "Como funciona" (`templates/presente/como_funciona.html`) ganha a seção "Quem faz o quê" com esta hierarquia.

### 7. Grupo "Servidor" (`users/signals.py`)
Mantém o grupo com permissões de `Activity`; as regras finas passam a ser de `permissions.py`. Alunos recebem apenas `add_activity` via fluxo de proposta (checado por `permissions`, não pelo grupo).

## Entrega sugerida (para revisar aos poucos)
1. Modelo + `permissions.py` + correção de "Minhas Atividades" + teto de pontos no formulário.
2. Proposta de aluno + tela de aprovações do organizador.
3. Trilhas e brindes pelo organizador.
4. Telas de regras globais do admin + menus + "Quem faz o quê".

## Verificação
- `python manage.py makemigrations --check` e `migrate` no SQLite local.
- Script de teste com `Client` dentro de `transaction.atomic()` + rollback (mesmo padrão usado nesta sessão), cobrindo:
  - servidor cria atividade com pontos acima do teto → erro; organizador consegue.
  - aluno propõe → atividade `PENDENTE`, check-in bloqueado, não aparece na trilha; organizador aprova → aparece e pontua.
  - organizador de outro evento recebe 403/404 nas telas do evento alheio.
  - servidor não vê o botão/rota de criar trilha; organizador cria trilha com bônus e a `gamificacao_bonus` é criada.
  - `is_staff` sem superuser não vê o menu ADMINISTRAÇÃO.
- Screenshots headless (Chrome) das telas novas: Meus eventos, Aprovações, Trilhas do evento, Propor atividade.
- Adicionar testes em `presente/tests.py` para `permissions.py` (hoje os 4 testes existentes já falhavam por atributos antigos do `PointService`; corrigir junto).
