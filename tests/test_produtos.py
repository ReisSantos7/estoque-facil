import tempfile
import unittest
import sqlite3
from pathlib import Path
from app import create_app
from domain import ProdutoRepository


class ProdutosTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'teste.db'
        self.app = create_app(self.path)
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.csrf = session['csrf']
        self.dados = dict(CODPROD='1001', DESCRPROD='Café torrado', CODVOL='UN', ESTMIN='5,5', csrf=self.csrf)

    def tearDown(self):
        self.tmp.cleanup()

    def cadastrar(self, **alteracoes):
        return self.client.post('/produtos/novo', data={**self.dados, **alteracoes}, follow_redirects=True)

    def test_cadastro_pesquisa_edicao_persistencia(self):
        self.assertEqual(self.cadastrar().status_code, 200)
        for termo in ['cafe', 'CAFÉ', '1001']:
            self.assertIn('Café torrado', self.client.get('/', query_string={'q': termo}).text)
        self.assertIn('Nenhum produto encontrado', self.client.get('/?q=inexistente').text)
        self.assertEqual(self.client.get('/produtos/1001/editar').status_code, 200)
        resposta = self.client.post('/produtos/1001/editar', data={**self.dados, 'DESCRPROD': 'Café especial', 'ESTMIN': '8', 'CODPROD': '9'}, follow_redirects=True)
        self.assertIn('atualizado com sucesso', resposta.text)
        nova = create_app(self.path).test_client()
        self.assertIn('Café especial', nova.get('/').text)
        registro = ProdutoRepository(str(self.path)).obter(1001)
        self.assertEqual(registro['ESTMIN'], 8)
        self.assertIsNone(ProdutoRepository(str(self.path)).obter(9))

    def test_codigo_duplicado_nao_sobrescreve(self):
        self.cadastrar()
        self.assertEqual(self.cadastrar(DESCRPROD='Outro').status_code, 422)
        self.assertEqual(ProdutoRepository(str(self.path)).obter(1001)['DESCRPROD'], 'Café torrado')

    def test_campos_invalidos(self):
        for alteracoes in [{'CODPROD':'0'}, {'CODPROD':'1.5'}, {'DESCRPROD':' '}, {'CODVOL':'INVALIDA'}, {'ESTMIN':'-1'}, {'ESTMIN':'NaN'}, {'ESTMIN':'inf'}, {'ESTMIN':'1.0001'}, {'ESTMIN':''}]:
            with self.subTest(alteracoes=alteracoes):
                self.assertEqual(self.cadastrar(**alteracoes).status_code, 422)
        self.assertEqual(len(ProdutoRepository(str(self.path)).buscar()), 0)

    def test_relacionamento_no_banco(self):
        repository = ProdutoRepository(str(self.path))
        with self.assertRaises(sqlite3.IntegrityError):
            with repository.conectar() as db:
                db.execute("INSERT INTO TGFPRO (CODPROD,DESCRPROD,CODVOL,ESTMIN) VALUES (1,'Teste','INVALIDA',0)")

    def test_seguranca_formulario_e_html(self):
        self.assertEqual(self.client.post('/produtos/novo', data={}).status_code, 400)
        resposta = self.cadastrar(DESCRPROD='<script>alert(1)</script>')
        self.assertNotIn('<script>alert(1)</script>', resposta.text)
        self.assertIn('&lt;script&gt;', resposta.text)
        self.assertEqual(self.client.get('/produtos/999/editar').status_code, 404)


if __name__ == '__main__':
    unittest.main()
