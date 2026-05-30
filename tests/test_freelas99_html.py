from __future__ import annotations

from openfreela.freelas99_html import parse_result_item_html

PROJECT_HREF = (
    "/project/alteracao-contratual-de-ltda-correcao-de-dbe-e-protocolo-na-"
    "jucemg-757057?fs=t"
)

RESULT_ITEM_HTML = f"""
<li class="with-flag result-item" data-id="757057">
  <hgroup>
    <h1 class="title">
      <a href="{PROJECT_HREF}">
        Alteração contratual de LTDA - correção de DBE e protocolo na JUCEMG
      </a>
    </h1>
    <p class="item-text information">
      Vídeo - Edição e Produção | Intermediário | Publicado:
      <b class="datetime" cp-datetime="1780142145000">7 horas atrás</b>
      | Tempo restante:
      <b class="datetime-restante" cp-datetime="1782732304000">
        29 dias e 15 horas
      </b>
      | Propostas: <b>10</b> | Interessados: <b>13</b>
    </p>
  </hgroup>
  <div class="item-text description formatted-text" data-content="">
    Procuro um profissional experiente em legalização de empresas.<br><br>
    O contrato de alteração já está redigido
    <span class="read-more" style="display: inline;">…
      <a href="#" class="more-link">Expandir</a>
    </span>
    <span class="details" style="display: none;">
      O que o profissional precisará fazer:<br>
      - Análise e correção do DBE.<br>
      - Integração na JUCEMG.<br>
      <span class="read-less"><a href="#" class="less-link">Esconder</a></span>
    </span>
  </div>
  <p class="item-text habilidades">
    <a class="habilidade" href="/projects?q=contabilidade">Contabilidade</a>
    <a class="habilidade" href="/projects?q=contabilidade%20tributaria">
      Contabilidade Tributária
    </a>
  </p>
</li>
"""


def test_parse_result_item_html_uses_structured_project_fields() -> None:
    item = parse_result_item_html(RESULT_ITEM_HTML)

    assert item is not None
    assert item.title == (
        "Alteração contratual de LTDA - correção de DBE e protocolo na JUCEMG"
    )
    assert item.project_href == PROJECT_HREF
    assert item.posted_at == "7 horas atrás"


def test_parse_result_item_html_extracts_information_fields() -> None:
    item = parse_result_item_html(RESULT_ITEM_HTML)

    assert item is not None
    assert item.level == "Intermediário"
    assert item.remaining_time == "29 dias e 15 horas"
    assert item.proposals == 10
    assert item.interested == 13


def test_parse_result_item_html_captures_expanded_description_without_controls() -> (
    None
):
    item = parse_result_item_html(RESULT_ITEM_HTML)

    assert item is not None
    assert "Procuro um profissional experiente" in item.description
    assert "O que o profissional precisará fazer" in item.description
    assert "Análise e correção do DBE" in item.description
    assert "Expandir" not in item.description
    assert "Esconder" not in item.description


def test_parse_result_item_html_extracts_habilidades_as_skills() -> None:
    item = parse_result_item_html(RESULT_ITEM_HTML)

    assert item is not None
    assert item.skills == ("Contabilidade", "Contabilidade Tributária")


def test_parse_result_item_html_returns_none_without_project_data() -> None:
    assert parse_result_item_html("<li>No structured project fields</li>") is None
