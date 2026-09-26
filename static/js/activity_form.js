"use strict";

document.addEventListener("DOMContentLoaded", function () {
  const evento = document.getElementById("id_evento");
  const trilha = document.getElementById("id_trilha");
  const pontos = document.getElementById("id_pontos");
  const area = document.getElementById("id_area");
  const preview = document.getElementById("gamificacao-preview");
  if (!trilha || !preview) return;

  const list = preview.querySelector("ul");

  function filtrarTrilhas() {
    const eventoId = evento ? evento.value : "";
    Array.from(trilha.options).forEach(function (opt) {
      const trilhaEvento = opt.dataset.evento;
      const visivel = !opt.value || !trilhaEvento || trilhaEvento === eventoId;
      opt.hidden = !visivel;
      opt.disabled = !visivel;
    });
    const selecionada = trilha.selectedOptions[0];
    if (selecionada && selecionada.disabled) trilha.value = "";
  }

  function item(icone, html, classe) {
    const li = document.createElement("li");
    if (classe) li.className = classe;
    li.innerHTML = '<i class="bi bi-' + icone + '"></i> <span></span>';
    li.querySelector("span").innerHTML = html;
    list.appendChild(li);
  }

  function texto(valor) {
    const span = document.createElement("span");
    span.textContent = valor;
    return span.innerHTML;
  }

  function atualizarPrevia() {
    list.innerHTML = "";
    const p = parseInt(pontos && pontos.value, 10) || 0;
    if (p > 0) {
      item("star-fill", "<strong>+" + p + " pts</strong> ao registrar presença");
    } else {
      item("dash-circle", "Esta atividade não dá pontos", "text-muted");
    }

    const opt = trilha.selectedOptions[0];
    if (opt && opt.value) {
      const bonus = parseInt(opt.dataset.bonus, 10) || 0;
      const minimo = parseInt(opt.dataset.minimo, 10) || 1;
      let msg = "Aparece na trilha <strong>" + texto(opt.textContent) + "</strong>";
      if (bonus) {
        msg += " · completando " + minimo + " atividade" + (minimo > 1 ? "s" : "") +
          " da trilha ganha <strong>+" + bonus + " pts</strong>";
      }
      if (opt.dataset.evento) msg += " <small class=\"text-muted\">(só para quem escolher a trilha)</small>";
      item("signpost-split-fill", msg);
    } else {
      item("signpost-split", "Não faz parte de nenhuma trilha", "text-muted");
    }

    if (area && area.value) {
      const nome = texto(area.selectedOptions[0].textContent);
      item("bookmark-fill", "Área <strong>" + nome + "</strong> · conta para o bônus de diversidade");
    }
  }

  if (evento) {
    evento.addEventListener("change", function () {
      filtrarTrilhas();
      atualizarPrevia();
    });
  }
  [trilha, pontos, area].forEach(function (el) {
    if (!el) return;
    el.addEventListener("input", atualizarPrevia);
    el.addEventListener("change", atualizarPrevia);
  });

  filtrarTrilhas();
  atualizarPrevia();
});
