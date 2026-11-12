# E2 Review — roteiro de entrega

Autor: Vinicius Reis dos Santos.

A atividade pede vídeo de **no máximo 3 minutos** mostrando o Scrum Board, os status das histórias e tarefas da Sprint 2 e o sistema funcionando com as histórias implementadas. Entrega: link do vídeo.

Na imagem enviada, as histórias da Sprint 2 são:

| Jira | História | Demonstração |
|---|---|---|
| SCRUM-5 | Cadastrar produtos | Produtos → Novo produto → Salvar |
| SCRUM-6 | Pesquisar produtos | Busca em Produtos e em Consulta de Produtos |
| SCRUM-7 | Editar produtos | Produtos → Editar → Salvar alterações |

As demais funcionalidades já estão implementadas no pacote. Não é necessário demonstrar todas no vídeo desta sprint se não fazem parte do escopo planejado dela.

## Antes de gravar

1. Execute o sistema e valide as três histórias no seu computador.
2. Atualize as subtarefas correspondentes no Jira; depois atualize as histórias cujos critérios foram atendidos.
3. Não conclua tarefas de documentação, GitHub ou outras atividades apenas porque o código está pronto: confirme cada entrega.
4. Mantenha os itens da Sprint 2 identificáveis para a gravação. Registre separadamente a implementação antecipada das demais histórias, sem mudar retroativamente o planejamento para aparentar que tudo foi previsto na Sprint 2.
5. Faça um ensaio. Use um código de produto ainda não cadastrado no vídeo.

## Roteiro de 2min50s

- **0:00–0:15:** apresente nome, Estoque Fácil e objetivo da Sprint 2.
- **0:15–0:45:** mostre o Scrum Board e abra uma história para mostrar subtarefas e status reais.
- **0:45–1:25:** em Produtos, cadastre código 1002 (ou outro livre), Arroz branco 5 kg, UN, grupo Geral, mínimo 10. Mostre a confirmação.
- **1:25–1:55:** pesquise por “arroz” e pelo código; abra Consulta de Produtos e faça a mesma busca. Um produto sem entradas tem saldo zero.
- **1:55–2:25:** volte a Produtos, edite a descrição ou mínimo, salve e pesquise novamente para mostrar a persistência.
- **2:25–2:50:** explique que o sistema usa Python, Flask e SQLite, roda localmente e possui os módulos de compras, vendas e extrato disponíveis para as demais histórias.

## Conferência das oito histórias

| Jira | Implementação disponível | Teste manual de aceite |
|---|---|---|
| SCRUM-5 | Produtos: cadastro | Salvar produto e rejeitar código repetido |
| SCRUM-6 | Duas telas de pesquisa | Buscar por nome/código e tratar resultado vazio |
| SCRUM-7 | Produtos: edição | Salvar e recarregar sem perder alteração |
| SCRUM-8 | Portal de Compras | Confirmar entrada de 10 unidades |
| SCRUM-9 | Portal de Vendas | Confirmar saída de 7; bloquear saída superior ao saldo |
| SCRUM-10 | Consulta de Produtos | Ver saldo 3 após os movimentos |
| SCRUM-11 | Consulta de Produtos | Mínimo 5 e saldo 3 aparecem no filtro de estoque baixo |
| SCRUM-12 | Portais e Extrato | Encontrar entrada e saída por filtros e abrir as notas |

Publique o vídeo em serviço permitido pela disciplina, confira a permissão de acesso do professor e envie o link no E2 Review. O código não atualiza Jira nem publica/envia o vídeo automaticamente.
