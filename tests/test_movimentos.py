import sqlite3
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from app import create_app
from domain import ProdutoRepository, ProdutoService, NotaService, CadastroService


class MovimentosTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'banco.db'
        self.app=create_app(self.path)
        self.repo=ProdutoRepository(self.path)
        self.prod=ProdutoService(self.repo)
        self.notas=NotaService(self.repo)
        self.cad=CadastroService(self.repo)
        self.prod.salvar(dict(CODPROD='1',DESCRPROD='Café especial',CODVOL='UN',ESTMIN='5'))
        self.prod.salvar(dict(CODPROD='2',DESCRPROD='Arroz',CODVOL='KG',ESTMIN='2'))
        self.base=dict(CODPARC='1',NUMNOTA='42',DTNEG='2026-11-01',DTMOV='2026-11-01')

    def tearDown(self):
        self.tmp.cleanup()

    def criar(self,tip='C',qtd='10',prod='1',extra=None,**cab):
        portal='compras' if tip in ('C','O') else 'vendas'
        top={'C':'1100','V':'2100','O':'1000','P':'2000'}[tip]
        itens=[dict(CODPROD=prod,QTDNEG=qtd,VLRUNIT='3.25')]+(extra or [])
        return self.notas.salvar(portal,{**self.base,'CODTIPOPER':top,**cab},itens)

    def saldo(self,codigo=1):
        return next(r['ESTOQUE'] for r in self.repo.consulta({}) if r['CODPROD']==codigo)

    def entrada(self,qtd='10'):
        n=self.criar(qtd=qtd);self.notas.confirmar(n);return n

    def test_fluxo_entrada_saida_saldo_extrato(self):
        n=self.criar()
        self.assertEqual(self.saldo(),0)
        self.assertEqual(self.notas.extrato({}),[])
        self.notas.confirmar(n)
        v=self.criar('V','7',DTMOV='2026-11-02')
        self.notas.confirmar(v)
        self.assertEqual(self.saldo(),3)
        self.assertEqual(self.repo.consulta({'baixo':'1','q':'cafe'})[0]['CODPROD'],1)
        linhas=self.notas.extrato({'inicio':'2026-11-02','fim':'2026-11-02','produto':'1','grupo':'1','tipmov':'V','top':'2100'})
        self.assertEqual(len(linhas),1)
        self.assertEqual(linhas[0]['ANTERIOR'],10)
        self.assertEqual(linhas[0]['SALDO'],3)
        self.assertEqual(len(self.notas.listar('vendas',{'produto':'1','status':'L'})),1)
        self.assertEqual(self.notas.listar('compras',{'tipmov':'V'}),[])

    def test_repetir_confirmacao_nao_duplica(self):
        n=self.entrada()
        self.assertFalse(self.notas.confirmar(n))
        self.assertEqual(self.saldo(),10)
        self.assertEqual(len(self.notas.extrato({})),1)

    def test_insuficiencia_multiplos_itens_rollback_total(self):
        self.entrada()
        n=self.criar('V','3',extra=[dict(CODPROD='2',QTDNEG='1',VLRUNIT='2')])
        with self.assertRaisesRegex(ValueError,'insuficiente'):self.notas.confirmar(n)
        self.assertEqual(self.saldo(),10)
        self.assertEqual(self.saldo(2),0)
        self.assertEqual(self.notas.obter(n)[0]['STATUSNOTA'],'P')

    def test_produto_repetido_considera_soma_e_fracoes(self):
        self.entrada('0.3')
        n=self.criar('V','0.1',extra=[dict(CODPROD='1',QTDNEG='0.2',VLRUNIT='0')])
        self.notas.confirmar(n)
        self.assertEqual(self.saldo(),0)
        r=self.criar('V','0.001')
        with self.assertRaises(ValueError):self.notas.confirmar(r)

    def test_top_sem_estoque_e_historico(self):
        n=self.criar()
        self.cad.salvar('tops',dict(CODTIPOPER='1100',DESCROPER='Compra sem estoque',TIPMOV='C',ATUALEST='N'))
        self.notas.confirmar(n) # nota antiga mantém E
        self.assertEqual(self.saldo(),10)
        novo=self.criar();self.notas.confirmar(novo)
        self.assertEqual(self.saldo(),10)
        self.assertEqual(self.notas.obter(novo)[0]['ATUALEST'],'N')
        self.assertEqual(len(self.notas.extrato({})),1)

    def test_pedidos_nao_alteram_saldo(self):
        for mov in ('O','P'):
            self.notas.confirmar(self.criar(mov))
        self.assertEqual(self.saldo(),0)
        self.assertEqual(self.notas.extrato({}),[])

    def test_editar_pendente_e_preservar_versao_top(self):
        n=self.criar()
        self.cad.salvar('tops',dict(CODTIPOPER='1100',DESCROPER='Nova versão',TIPMOV='C',ATUALEST='N'))
        self.notas.salvar('compras',{**self.base,'CODTIPOPER':'1100'},[dict(CODPROD='2',QTDNEG='2',VLRUNIT='5')],n)
        cab,itens=self.notas.obter(n)
        self.assertEqual(cab['ATUALEST'],'E')
        self.assertEqual(cab['VLRNOTA'],10)
        self.assertEqual(len(itens),1)
        self.notas.confirmar(n)
        self.assertEqual(self.saldo(2),2)
        with self.assertRaises(ValueError):self.notas.excluir_pendente(n)
        with self.assertRaises(ValueError):self.notas.salvar('compras',{**self.base,'CODTIPOPER':'1100'},[],n)

    def test_excluir_pendente_remove_itens(self):
        n=self.criar();self.notas.excluir_pendente(n)
        self.assertEqual(self.notas.obter(n),(None,[]))
        self.assertEqual(self.saldo(),0)

    def test_unidade_bloqueada_quando_vinculada(self):
        self.criar()
        with self.assertRaisesRegex(ValueError,'unidade'):
            self.prod.salvar(dict(DESCRPROD='Café',CODVOL='KG',ESTMIN='3'),1)

    def test_validacoes_cabecalho_itens_e_top(self):
        for campos in [dict(CODTIPOPER='2100'),dict(CODPARC='999'),dict(DTMOV='invalida')]:
            with self.subTest(campos=campos), self.assertRaises(ValueError):self.criar(**campos)
        for q in ('0','-1','NaN','Infinity','0.0001'):
            with self.subTest(q=q),self.assertRaises(ValueError):self.criar(qtd=q)
        with self.assertRaises(ValueError):self.criar(prod='999')
        with self.assertRaises(ValueError):self.cad.salvar('tops',dict(CODTIPOPER='333',DESCROPER='Incompatível',TIPMOV='C',ATUALEST='B'))
        with self.assertRaises(ValueError):self.notas.extrato({'inicio':'2026-12-01','fim':'2026-01-01'})
        self.assertEqual(self.notas.listar('compras',{}),[])

    def test_concorrencia_nao_gasta_mesmo_saldo(self):
        self.entrada('10')
        a=self.criar('V','7');b=self.criar('V','7')
        def executar(n):
            try:return self.notas.confirmar(n)
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(executar,[a,b]))
        self.assertEqual(sum(results),1)
        self.assertEqual(self.saldo(),3)

    def test_paginas_e_fluxo_http(self):
        c=self.app.test_client();c.get('/')
        with c.session_transaction() as sess:token=sess['csrf']
        for url in ['/', '/produtos/novo','/produtos/1/editar','/consulta-produtos?q=cafe','/consulta-produtos?baixo=1',
                    '/portal/compras','/portal/vendas','/portal/compras/nova','/portal/vendas/nova',
                    '/grupos','/grupos?aba=cadastro','/cadastros/tops','/cadastros/parceiros']:
            with self.subTest(url=url):self.assertEqual(c.get(url).status_code,200)
        response=c.post('/portal/compras/nova',data={**self.base,'CODTIPOPER':'1100','csrf':token,'CODPROD':['1','2'],'QTDNEG':['5','3'],'VLRUNIT':['2','3']},follow_redirects=True)
        self.assertEqual(response.status_code,200)
        self.assertIn('Confirmar nota',response.text)
        n=self.notas.listar('compras',{})[0]['NUNOTA']
        self.assertEqual(c.get(f'/portal/compras/{n}/editar').status_code,200)
        self.assertEqual(c.post(f'/notas/{n}/confirmar',data={'csrf':token},follow_redirects=True).status_code,200)
        self.assertEqual(c.get(f'/portal/compras/{n}/editar').status_code,409)
        self.assertIn('5',c.get('/consulta-produtos').text)
        self.assertEqual(c.get('/grupos?inicio=2026-12-01&fim=2026-01-01').status_code,422)
        self.assertEqual(c.post('/portal/vendas/nova',data={}).status_code,400)

    def test_migracao_preserva_produtos_e_faz_backup(self):
        path=Path(self.tmp.name)/'antigo.db'
        with sqlite3.connect(path) as db:
            db.executescript("CREATE TABLE TGFVOL(CODVOL TEXT PRIMARY KEY,DESCRVOL TEXT);INSERT INTO TGFVOL VALUES('UN','Unidade');CREATE TABLE TGFPRO(CODPROD INTEGER PRIMARY KEY,DESCRPROD TEXT NOT NULL,CODVOL TEXT NOT NULL REFERENCES TGFVOL(CODVOL),ESTMIN REAL NOT NULL);INSERT INTO TGFPRO VALUES(50,'Produto antigo','UN',5);")
        r=ProdutoRepository(path);r.inicializar();r.inicializar()
        self.assertEqual(r.obter(50)['DESCRPROD'],'Produto antigo')
        self.assertEqual(r.obter(50)['CODGRUPOPROD'],1)
        self.assertEqual(len(list(Path(self.tmp.name).glob('antigo.db.antes-v2-*.bak'))),1)
        with r.conectar() as db:self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_grupos_parceiros_e_filtros(self):
        self.cad.salvar('grupos',dict(CODGRUPOPROD='2',DESCRGRUPOPROD='Alimentos'))
        self.cad.salvar('parceiros',dict(CODPARC='3',NOMEPARC='Mercado São José'))
        self.prod.salvar(dict(DESCRPROD='Café especial',CODVOL='UN',ESTMIN='5',CODGRUPOPROD='2'),1)
        n=self.criar(CODPARC='3');self.notas.confirmar(n)
        self.assertEqual(len(self.notas.listar('compras',{'q':'sao jose','parceiro':'3','top':'1100'})),1)
        self.assertEqual(len(self.notas.extrato({'grupo':'2'})),1)
        self.assertEqual(len(self.notas.extrato({'grupo':'1'})),0)
        self.assertEqual(len(self.repo.consulta({'grupo':'2'})),1)

    def test_persistencia_nota_e_estoque(self):
        n=self.entrada()
        create_app(self.path)
        self.assertEqual(self.notas.obter(n)[0]['STATUSNOTA'],'L')
        self.assertEqual(self.saldo(),10)

if __name__=='__main__':unittest.main()
