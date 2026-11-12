# Dicionário de dados — Estoque Fácil

Esquema relacional acadêmico do Estoque Fácil. Tipos, limites, restrições e dados iniciais são definidos pelo projeto.

| Tabela | Chave primária | Campos utilizados / finalidade |
|---|---|---|
| TGFPRO | CODPROD | DESCRPROD, CODVOL, ESTMIN, CODGRUPOPROD — cadastro |
| TGFVOL | CODVOL | DESCRVOL — unidade |
| TGFGRU | CODGRUPOPROD | DESCRGRUPOPROD — grupo |
| TGFCAB | NUNOTA | NUMNOTA, CODEMP, CODPARC, DTNEG, DTMOV, CODTIPOPER, DHTIPOPER, TIPMOV, STATUSNOTA, VLRNOTA, OBSERVACAO — cabeçalho |
| TGFITE | NUNOTA + SEQUENCIA | CODEMP, CODPROD, CODLOCALORIG, CONTROLE, CODVOL, QTDNEG, VLRUNIT, VLRTOT — itens |
| TGFTOP | CODTIPOPER + DHALTER | DESCROPER, TIPMOV, ATUALEST — operação e versão |
| TGFEST | CODEMP + CODLOCAL + CODPROD + CONTROLE + TIPO + CODPARC | ESTOQUE, RESERVADO — saldo |
| TGFPAR | CODPARC | NOMEPARC — cliente/fornecedor |
| TSIEMP | CODEMP | RAZAOSOCIAL — empresa |
| TGFLOC | CODLOCAL | DESCRLOCAL — local |

Relações: produto pertence a grupo e unidade; cabeçalho pertence a parceiro, empresa e versão da TOP; itens pertencem ao cabeçalho, produto, unidade, local e empresa. O estoque referencia produto, empresa, local e parceiro. Chaves estrangeiras são habilitadas em cada conexão.

## Convenções locais

- DATAS: texto ISO; DHALTER inclui hora e microssegundos. DHTIPOPER guarda a versão utilizada.
- TIPMOV: C compra, V venda, O pedido de compra, P pedido de venda.
- ATUALEST no projeto: E entrada, B baixa, N sem atualização. Compras aceitam E/N; vendas B/N; pedidos N.
- STATUSNOTA: P pendente, L confirmada. O projeto não implementa outros estados.
- Estoque: empresa/local 1; CONTROLE contém um espaço; TIPO=P; CODPARC=0; RESERVADO=0.
- Quantidades e valores são armazenados como REAL, adaptados ao SQLite. Operações no serviço usam Decimal; valores são limitados e arredondados. Essa adaptação não é indicada como motor contábil de produção.
- O extrato é uma consulta às notas e itens confirmados associados à TOP; não existe uma tabela fictícia de movimentações.
- Não existe edição direta do saldo. Entradas e saídas passam pela confirmação da nota.

O SQL exato e suas restrições estão em `schema.sql`. Produtos migrados da primeira versão recebem CODGRUPOPROD=1. O banco antigo recebe backup antes da migração.

Fontes oficiais usadas para nomes e relacionamentos:

