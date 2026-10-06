# 8 de outubro — Reserva e submissão do Sprint 3

## Estado técnico final

Preparado antecipadamente em 6 de outubro de 2026 para a submissão prevista de
8 de outubro de 2026.

- Suite completa: **256 testes aprovados**, zero falhas e zero erros.
- SQLite `PRAGMA integrity_check`: **ok**.
- SQLite `PRAGMA foreign_key_check`: **0 violações**.
- Empresas: **92**.
- Registos em `financial_ratios`: **1.155**.
- Peer groups: **11**, com **11 benchmarks oficiais**.
- Empresas com peer group: **56**.
- Empresas sem peer group: **36**, tratadas pela média do Nifty 100.
- Registos em `peer_percentiles`: **7.060**.
- Presets implementados: **6** e executados sobre as 92 empresas.
- Radar charts: **92**, todos não vazios e com nomes únicos.
- `screener_output.xlsx`: **6 folhas**, todas não vazias.
- `peer_comparison.xlsx`: **11 folhas**, todas não vazias.
- Pacote público: nenhum ficheiro de dados, base SQLite, Excel, CSV ou gráfico
  confidencial encontrado.

## Exceções documentadas

Os thresholds oficiais não foram alterados para fabricar resultados. Quatro
presets ficaram dentro do intervalo de 5–50 empresas. `Value Pick` e
`Debt-Free Blue Chip` devolveram duas empresas cada. A investigação e as regras
limitantes estão documentadas em `preset_diagnostics.csv` e no relatório de
validação.

## Checklist técnica concluída

- [x] Executar a suite completa de testes.
- [x] Confirmar integridade e chaves estrangeiras do SQLite.
- [x] Confirmar 92 empresas.
- [x] Confirmar 11 peer groups e 11 benchmarks.
- [x] Confirmar os seis presets e respetivos relatórios.
- [x] Confirmar 92 radar charts válidos.
- [x] Confirmar seis folhas no screener Excel.
- [x] Confirmar 11 folhas no peer comparison Excel.
- [x] Auditar o pacote público contra conteúdo confidencial.
- [x] Preparar pacote público e pacote confidencial separadamente.
- [x] Preparar documentação, evidências, outputs, gráficos e base final.

## Ações externas pendentes

Estas ações exigem acesso autenticado da responsável pela submissão:

- [ ] Atualizar o GitHub usando apenas o pacote GitHub Safe.
- [ ] Confirmar no GitHub que não existem dados confidenciais.
- [ ] Copiar o endereço real do projeto para `GITHUB_LINK.txt`.
- [ ] Carregar a pasta final completa no Google Drive consolidado.
- [ ] Definir a pasta como `Anyone with the link — Viewer`.
- [ ] Testar GitHub e Google Drive numa janela anónima.
- [ ] Colar a Note to Admin preparada.
- [ ] Submeter o link do Google Drive no Workspace.
- [ ] Confirmar o estado `Submitted` e guardar uma captura de ecrã.
- [ ] Enviar o Standup final somente depois da confirmação da submissão.

## Ordem segura de submissão

1. Atualizar o GitHub com o pacote público.
2. Copiar o URL real do projeto para `GITHUB_LINK.txt`.
3. Colocar o `GITHUB_LINK.txt` atualizado na pasta principal de submissão.
4. Carregar a pasta principal completa no Google Drive consolidado.
5. Testar ambos os links em janela anónima.
6. Colar a Note to Admin e submeter o link do Drive no Workspace.
7. Guardar evidência de `Submitted` antes de enviar o Standup final.

