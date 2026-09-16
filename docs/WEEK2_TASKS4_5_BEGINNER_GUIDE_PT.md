# Guia simples das tarefas 4 e 5 da Week 2

## Tarefa 4  Diagrama de arquitetura de software

### O que a tarefa pediu

Criar um diagrama simples mostrando como os dados saem de uma ação do utilizador numa aplicação web, passam pelo sistema e chegam a um dashboard analítico.

### Como o diagrama foi construído

1. **Ação do utilizador:** o processo começa quando uma pessoa entra na aplicação, coloca uma ordem ou abre a carteira.
2. **Frontend:** é a parte visível no navegador ou telefone. Ela recebe a ação e mostra o resultado.
3. **Autenticação e REST API:** o servidor confirma a identidade, as permissões e se o pedido está no formato correto.
4. **Backend:** aplica regras de negócio, validações e controlos de risco.
5. **Base de dados operacional:** guarda utilizadores, ordens, transações e estados.
6. **Data pipeline:** extrai, valida, limpa e transforma os dados.
7. **Analytics store:** conserva dados históricos preparados e consistentes.
8. **Dashboard:** transforma os dados em KPIs, tendências, relatórios e alertas.

O diagrama também inclui **logging** e **error handling**. Logging guarda registos do que aconteceu; error handling trata falhas e apresenta mensagens claras sem comprometer os dados.

## Tarefa 5  Pesquisa sobre uma FinTech indiana

### Por que foi escolhida a Zerodha

A Zerodha é uma plataforma indiana de corretagem que liga os principais conceitos exigidos na tarefa: corretora, conta de negociação, conta demat, depositários, SEBI, ciclo da negociação, liquidação e participantes do mercado.

### Como a pesquisa foi feita

1. Foram consultadas páginas oficiais da Zerodha sobre a empresa e os produtos.
2. Foram analisadas as documentações oficiais do Kite, Console e Kite Connect.
3. A explicação sobre trading account, demat account, CDSL, NSDL e SEBI foi confirmada em fontes oficiais.
4. Foram separados os fatos publicados das interpretações. Por exemplo, é fato que Console oferece P&L, relatórios fiscais e visualizações. A redução de trabalho manual é um benefício analítico razoável, mas não foi apresentada como uma métrica interna da empresa.
5. O relatório foi organizado em plataforma, ecossistema, fontes de dados, aplicações analíticas, benefícios, riscos e conclusão.

### O que deves saber explicar numa apresentação

- **Frontend** é aquilo que o utilizador vê e usa.
- **Backend** processa os pedidos e aplica regras.
- **API** permite que sistemas troquem informações de forma estruturada.
- **Database** guarda os dados operacionais.
- **Data pipeline** prepara os dados para análise.
- **Dashboard** apresenta resultados de forma visual.
- **Brokerage platform** recebe e encaminha ordens de compra e venda.
- **Trading account** é usada para negociar; **demat account** guarda títulos eletronicamente.
- **NSDL e CDSL** são depositários; o investidor acede a eles através de um Depository Participant.
- **SEBI** regula o mercado de valores mobiliários e os intermediários.
- A Zerodha usa dados de mercado, ordens, transações e carteiras para fornecer gráficos, P&L, relatórios fiscais, alertas e avisos de risco.

## Ficheiros finais

- `Week2_Task4_Software_Architecture_Diagram.pdf`
- `Week2_Task4_Software_Architecture_Diagram.png`
- `Week2_Task5_Zerodha_FinTech_Research_Report.pdf`
- `Week2_Task5_Zerodha_FinTech_Research_Report.docx`
