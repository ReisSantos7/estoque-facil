from test_movimentos import MovimentosTest
from domain import GerenciamentoService
from explorer import DatabaseExplorer

class GerenciamentoTest(MovimentosTest):
    def test_exclusao_e_reversao(self):
        g=GerenciamentoService(self.repo)
        compra=self.entrada()
        venda=self.criar('V','4');self.notas.confirmar(venda)
        with self.assertRaises(ValueError):self.notas.excluir(compra)
        self.assertEqual(self.saldo(),6)
        self.assertIsNotNone(self.notas.obter(compra)[0])
        with self.assertRaises(ValueError):g.excluir('produtos',1)
        self.notas.excluir(venda);self.assertEqual(self.saldo(),10)
        self.notas.excluir(compra);self.assertEqual(self.saldo(),0)
        g.excluir('produtos',1);self.assertIsNone(self.repo.obter(1))
        with self.repo.conectar() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM TGFITE').fetchone()[0],0)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_excluir_pedido_e_seed_nao_retorna(self):
        n=self.criar('O');self.notas.confirmar(n);self.notas.excluir(n)
        self.assertEqual(self.saldo(),0)
        g=GerenciamentoService(self.repo)
        g.excluir('tops',1000);g.excluir('parceiros',2)
        self.repo.inicializar()
        self.assertFalse(any(x['CODTIPOPER']==1000 for x in self.repo.tops()))
        self.assertFalse(any(x['CODPARC']==2 for x in self.repo.listar('TGFPAR')))

    def test_rollback_exclusao_varios_itens(self):
        compra=self.criar(extra=[dict(CODPROD='2',QTDNEG='5',VLRUNIT='1')])
        self.notas.confirmar(compra)
        venda=self.criar('V','2',prod='2');self.notas.confirmar(venda)
        with self.assertRaises(ValueError):self.notas.excluir(compra)
        self.assertEqual(self.saldo(),10);self.assertEqual(self.saldo(2),3)

    def test_explorer_bloqueia_escrita_e_ve_saldo(self):
        e=DatabaseExplorer(self.path)
        self.assertIn('TGFEST',e.tabelas())
        for sql in ["DELETE FROM TGFPRO","UPDATE TGFPRO SET ESTMIN=0",
                    "DROP TABLE TGFPRO","PRAGMA query_only=OFF","ATTACH ':memory:' AS outro",
                    "SELECT load_extension('x')","SELECT 1; DELETE FROM TGFPRO",
                    "WITH x AS (SELECT 1) DELETE FROM TGFPRO",
                    "SELECT * FROM pragma_table_info('TGFPRO')"]:
            with self.subTest(sql=sql),self.assertRaises(ValueError):e.consultar(sql)
        self.entrada()
        self.assertEqual(e.consultar('SELECT ESTOQUE FROM TGFEST')['linhas'][0][0],10)
        self.assertEqual(e.consultar('WITH x AS (SELECT COUNT(*) AS N FROM TGFPRO) SELECT N FROM x')['linhas'][0][0],2)
        self.assertTrue(e.consultar('WITH RECURSIVE x(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM x WHERE n<600) SELECT * FROM x')['limitado'])
        with self.assertRaises(ValueError):
            e.consultar('WITH RECURSIVE x(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM x) SELECT sum(n) FROM x')

    def test_rotas_novas(self):
        c=self.app.test_client()
        self.assertEqual(c.get('/dbexplorer').status_code,200)
        with c.session_transaction() as s:token=s['csrf']
        self.assertEqual(c.post('/dbexplorer',data={'csrf':token,'sql':'SELECT * FROM TGFPRO'}).status_code,200)
        self.assertEqual(c.post('/dbexplorer',data={'csrf':token,'sql':'DELETE FROM TGFPRO'}).status_code,422)
        self.assertEqual(c.post('/gerenciar/produtos/2/excluir').status_code,400)
        self.assertIn('Registro excluído',c.post('/gerenciar/produtos/2/excluir',data={'csrf':token},follow_redirects=True).text)
        n=self.entrada()
        self.assertIn('Excluir nota',c.get(f'/notas/{n}').text)
        self.assertEqual(c.post(f'/notas/{n}/excluir',data={'csrf':token}).status_code,302)
        self.assertEqual(self.saldo(),0)
