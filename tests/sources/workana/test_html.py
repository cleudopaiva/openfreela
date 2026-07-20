from __future__ import annotations

from openfreela.sources.workana.html import parse_project_item_html

WORKANA_CARD_HTML = """
<div class="project-item js-project project-item-featured">
  <div class="project-header">
    <h2 class="h3 project-title">
      <span>
        <a href="/job/profissional-experiente-em-nuvemshop" target="_blank">
          <span title="Profissional Experiente em Nuvemshop">
            Profissional Experiente em Nuvemshop...
          </span>
        </a>
      </span>
    </h2>
  </div>
  <div class="project-body">
    <div class="project-main-details hidden-xs small">
      <span class="date">Publicado: há 3 horas</span>
      <span class="bids">Propostas: 19</span>
    </div>
    <div class="html-desc project-details">
      <p class="text-expander-content">
        <span>Estamos buscando um profissional para otimizar loja virtual.</span>
        <span>...</span>
        <a href="#" class="link small">Ver mais detalhes</a>
      </p>
    </div>
    <div class="skills">
      <a class="skill label label-info"><h3>HTML</h3></a>
      <a class="skill label label-info"><h3>JavaScript</h3></a>
    </div>
  </div>
  <div class="project-actions floating">
    <p class="budget h4"><span class="values"><span>USD 250 - 500</span></span></p>
  </div>
</div>
"""


def test_parse_project_item_html_extracts_workana_fields() -> None:
    item = parse_project_item_html(WORKANA_CARD_HTML)

    assert item is not None
    assert item.title == "Profissional Experiente em Nuvemshop"
    assert item.project_href == "/job/profissional-experiente-em-nuvemshop"
    assert item.posted_at == "há 3 horas"
    assert item.proposals == 19
    assert item.budget == "USD 250 - 500"
    assert item.skills == ("HTML", "JavaScript")
    assert item.description == (
        "Estamos buscando um profissional para otimizar loja virtual."
    )


def test_parse_project_item_html_returns_none_without_project_data() -> None:
    assert parse_project_item_html("<div>No project data</div>") is None
