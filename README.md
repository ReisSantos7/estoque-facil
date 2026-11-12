# Estoque Fácil

Projeto acadêmico desenvolvido para a disciplina PDS.

**Autor:** Vinicius Reis dos Santos.

## Objetivo

Desenvolver um sistema de gestão de estoque que permita cadastrar,
pesquisar e editar produtos, registrar entradas e saídas, consultar
saldos, identificar produtos abaixo do estoque mínimo e acompanhar
o histórico de movimentações.

A aplicação funciona localmente, sem custo de hospedagem.

## Tecnologias utilizadas

- Python 3.14: linguagem de programação.
- Flask: desenvolvimento da aplicação web.
- SQLite: banco de dados relacional.
- HTML e Jinja2: estrutura das páginas e templates.
- CSS: apresentação visual das telas.
- JavaScript: interações da interface.
- Git e GitHub: versionamento e armazenamento do código.

## Funcionalidades

- Cadastro, pesquisa, edição e exclusão de produtos.
- Consulta de saldos e estoque baixo.
- Portal de Compras para registrar entradas.
- Portal de Vendas para registrar saídas.
- Configuração de tipos de operação.
- Cadastro de parceiros e grupos de produtos.
- Extrato de movimentações.
- Exclusão de notas com reversão do efeito no estoque.
- DBExplorer para consultas SQL somente de leitura.

## Organização do projeto

- app.py: rotas e interface web.
- domain.py: regras de negócio e acesso aos dados.
- explorer.py: consultas ao banco em modo somente leitura.
- schema.sql: estrutura do banco de dados.
- templates/: páginas HTML.
- static/: arquivos CSS e JavaScript.
- tests/: testes automatizados.
- docs/: documentação complementar.

## Banco de dados

O SQLite armazena produtos, grupos, parceiros, tipos de operação,
notas, itens e saldos de estoque em tabelas relacionadas por
chaves primárias e estrangeiras.

O banco é criado automaticamente em instance/estoque.db.

## Como executar no macOS

Pré-requisito: Python 3.14 instalado.

Na pasta do projeto, execute:

```bash
python3.14 -m venv .venv314
source .venv314/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Com o servidor em execução, acesse:

http://127.0.0.1:5000

## Testes automatizados

Com o ambiente virtual ativado, execute:

```bash
python -m unittest discover -s tests -v
```

## Regras de estoque

- Notas pendentes não movimentam estoque.
- A confirmação aplica o efeito do tipo de operação.
- Saídas sem saldo suficiente são bloqueadas.
- A exclusão de uma nota confirmada reverte seu efeito no estoque.
- Exclusões que causariam saldo negativo são bloqueadas.
- Registros vinculados possuem restrições de exclusão.

## Sprint 2

Funcionalidades previstas para demonstração:

- Cadastrar produtos.
- Pesquisar produtos.
- Editar produtos.

## Finalidade

Sistema acadêmico para demonstração local, sem emissão fiscal.
