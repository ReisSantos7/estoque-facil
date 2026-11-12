# Arquitetura — Estoque Fácil

Aplicação web monolítica local, com backend orientado a objetos e persistência relacional. As rotas HTTP ficam em app.py, as entidades/regras/acesso ao banco em domain.py, as páginas Jinja em templates e os recursos locais em static.

| Classe | Responsabilidade |
|---|---|
| Produto | Dados do produto |
| ItemNota | Dados do item e cálculo do total com Decimal |
| ProdutoRepository | Conexões, migração, consultas, persistência de produtos e tabelas de apoio |
| ProdutoService | Validação do cadastro e edição de produtos |
| CadastroService | Criação de grupos, parceiros e versões de TOP |
| NotaService | Lançamento, edição, confirmação transacional, consulta das notas e extrato |

## Confirmação de nota

1. Abre transação com BEGIN IMMEDIATE para serializar gravações concorrentes.
2. Lê a nota e sua versão da TOP; uma nota já confirmada retorna sem reaplicar efeitos.
3. Percorre os itens e aplica entrada/baixa sobre o saldo da chave de estoque.
4. Se faltar saldo em qualquer item, lança erro e desfaz todas as alterações.
5. Atualiza STATUSNOTA para L e confirma a transação.

Os movimentos são reconstituídos por TGFCAB/TGFITE/TGFTOP. O saldo atual fica em TGFEST. TOPs históricas permanecem vinculadas por CODTIPOPER/DHTIPOPER.

## Cuidados de implementação

SQL parametrizado, validação no servidor, escape automático HTML, token CSRF, chaves estrangeiras e servidor limitado a 127.0.0.1. Recursos estáticos locais permitem operar sem internet depois da instalação. A aplicação é demonstrativa e não possui login, autorização por usuário ou infraestrutura de produção.

## Validação executada

20 testes automatizados aprovados: cadastro, pesquisa sem acentos, edição, persistência, duplicidade, campos inválidos, relacionamentos, CSRF/HTML, entrada/saída, saldo, extrato, TOP sem estoque, histórico da TOP, pedidos, edição/exclusão de pendentes, bloqueio de unidade, rollback de múltiplos itens, quantidades fracionadas, concorrência e migração do banco anterior. Os testes de rotas verificam renderização HTTP; não substituem a conferência visual no navegador do usuário.
