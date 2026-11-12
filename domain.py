"""Domínio e repositório do Estoque Fácil. Esquema acadêmico de gestão de estoque."""
import sqlite3
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from contextlib import contextmanager
from pathlib import Path
from datetime import date, datetime

TIPOS = {'C': 'Compra', 'V': 'Venda', 'O': 'Pedido de compra', 'P': 'Pedido de venda'}
EFEITOS = {'E': 'Entrada', 'B': 'Baixa', 'N': 'Não atualiza'}


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(texto).casefold()) if not unicodedata.combining(c))


def inteiro(valor, nome, minimo=1, maximo=9999999999):
    try:
        n = int(str(valor))
        if not minimo <= n <= maximo:
            raise ValueError()
        return n
    except (ValueError, TypeError):
        raise ValueError(f'{nome}: informe um inteiro entre {minimo} e {maximo}.')


def numero(valor, nome, casas=3, positivo=False):
    try:
        n = Decimal(str(valor).strip().replace(',', '.'))
        if not n.is_finite() or not 0 <= n <= 999999999 or (positivo and n == 0):
            raise InvalidOperation()
        if n != n.quantize(Decimal(1).scaleb(-casas)):
            raise InvalidOperation()
        return n
    except (ValueError, InvalidOperation):
        raise ValueError(f'{nome}: informe um número {"maior que zero" if positivo else "não negativo"}, até 999999999 e com até {casas} casas decimais.')


def data_iso(valor):
    try:
        return date.fromisoformat(str(valor)).isoformat()
    except ValueError:
        raise ValueError('Informe uma data válida.')


def periodo(filtros):
    inicio = data_iso(filtros['inicio']) if filtros.get('inicio') else ''
    fim = data_iso(filtros['fim']) if filtros.get('fim') else ''
    if inicio and fim and inicio > fim:
        raise ValueError('A data inicial deve ser anterior ou igual à final.')
    return inicio, fim


@dataclass(frozen=True)
class Produto:
    CODPROD: int
    DESCRPROD: str
    CODVOL: str
    ESTMIN: float
    CODGRUPOPROD: int = 1


@dataclass(frozen=True)
class ItemNota:
    CODPROD: int
    CODVOL: str
    QTDNEG: Decimal
    VLRUNIT: Decimal

    @property
    def total(self):
        return (self.QTDNEG * self.VLRUNIT).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


class ProdutoRepository:
    def __init__(self, caminho):
        self.caminho = str(caminho)

    @contextmanager
    def conectar(self):
        conexao = sqlite3.connect(self.caminho, timeout=15)
        conexao.row_factory = sqlite3.Row
        conexao.execute('PRAGMA foreign_keys = ON')
        conexao.create_function('NORMALIZAR', 1, normalizar)
        try:
            with conexao:
                yield conexao
        finally:
            conexao.close()

    def inicializar(self):
        with self.conectar() as db:
            existente = db.execute("SELECT name FROM sqlite_master WHERE name='TGFPRO'").fetchone()
            migrar = existente and 'CODGRUPOPROD' not in {r['name'] for r in db.execute('PRAGMA table_info(TGFPRO)')}
            if migrar:
                # Backup do arquivo anterior, antes de qualquer alteração de esquema.
                backup = self.caminho + '.antes-v2-' + datetime.now().strftime('%Y%m%d%H%M%S%f') + '.bak'
                with sqlite3.connect(backup) as destino:
                    db.backup(destino)
            if migrar:
                db.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE IF NOT EXISTS TGFGRU(CODGRUPOPROD INTEGER PRIMARY KEY CHECK(CODGRUPOPROD>0), DESCRGRUPOPROD TEXT NOT NULL);
                    INSERT OR IGNORE INTO TGFGRU VALUES (1,'Geral');
                    CREATE TABLE TGFPRO_V2(
                        CODPROD INTEGER PRIMARY KEY CHECK(CODPROD BETWEEN 1 AND 9999999999),
                        DESCRPROD TEXT NOT NULL CHECK(length(trim(DESCRPROD)) BETWEEN 1 AND 100),
                        CODVOL TEXT NOT NULL REFERENCES TGFVOL(CODVOL),
                        ESTMIN REAL NOT NULL DEFAULT 0 CHECK(ESTMIN BETWEEN 0 AND 999999999),
                        CODGRUPOPROD INTEGER NOT NULL DEFAULT 1 REFERENCES TGFGRU(CODGRUPOPROD));
                    INSERT INTO TGFPRO_V2 SELECT CODPROD,DESCRPROD,CODVOL,ESTMIN,1 FROM TGFPRO;
                    DROP TABLE TGFPRO;
                    ALTER TABLE TGFPRO_V2 RENAME TO TGFPRO;
                    COMMIT;
                """)
            db.executescript(Path(__file__).with_name('schema.sql').read_text())
            db.execute("CREATE TABLE IF NOT EXISTS APP_CONFIG (CHAVE TEXT PRIMARY KEY, VALOR TEXT NOT NULL)")
            if not db.execute("SELECT 1 FROM APP_CONFIG WHERE CHAVE='cadastros_iniciais'").fetchone():
                db.execute("INSERT OR IGNORE INTO TGFGRU VALUES (1,'Geral')")
                db.executemany('INSERT OR IGNORE INTO TGFVOL VALUES (?,?)', [('UN','Unidade'),('KG','Quilograma'),('L','Litro'),('CX','Caixa')])
                db.execute("INSERT OR IGNORE INTO TSIEMP VALUES (1,'Estoque Fácil — demonstração')")
                db.execute("INSERT OR IGNORE INTO TGFLOC VALUES (1,'Depósito principal')")
                db.executemany('INSERT OR IGNORE INTO TGFPAR VALUES (?,?)', [(0,'Estoque próprio'),(1,'Fornecedor demonstração'),(2,'Cliente demonstração')])
                db.executemany('INSERT OR IGNORE INTO TGFTOP VALUES (?,?,?,?,?)', [
                    (1100,'2026-01-01T00:00:00','Compra com entrada','C','E'),
                    (2100,'2026-01-01T00:00:00','Venda com baixa','V','B'),
                    (1000,'2026-01-01T00:00:00','Pedido de compra','O','N'),
                    (2000,'2026-01-01T00:00:00','Pedido de venda','P','N')])
                db.execute("INSERT INTO APP_CONFIG VALUES ('cadastros_iniciais','1')")

    def listar(self, tabela):
        permitidas = {'TGFVOL':'DESCRVOL','TGFGRU':'DESCRGRUPOPROD','TGFPAR':'NOMEPARC'}
        if tabela not in permitidas:
            raise ValueError('Tabela não permitida.')
        with self.conectar() as db:
            return [dict(r) for r in db.execute(f'SELECT * FROM {tabela} ORDER BY {permitidas[tabela]}')]

    def unidades(self):
        return self.listar('TGFVOL')

    def buscar(self, termo=''):
        with self.conectar() as db:
            return [dict(r) for r in db.execute('''SELECT P.*,G.DESCRGRUPOPROD FROM TGFPRO P
                JOIN TGFGRU G ON G.CODGRUPOPROD=P.CODGRUPOPROD
                WHERE instr(NORMALIZAR(P.DESCRPROD),NORMALIZAR(?))>0 OR CAST(CODPROD AS TEXT)=? ORDER BY CODPROD''', (termo,termo))]

    def obter(self, codigo):
        with self.conectar() as db:
            r = db.execute('SELECT * FROM TGFPRO WHERE CODPROD=?',(codigo,)).fetchone()
            return dict(r) if r else None

    def salvar(self, p, editar=False):
        with self.conectar() as db:
            db.execute('BEGIN IMMEDIATE')
            valores = (p.DESCRPROD,p.CODVOL,p.ESTMIN,p.CODGRUPOPROD,p.CODPROD)
            if editar:
                antigo = db.execute('SELECT * FROM TGFPRO WHERE CODPROD=?',(p.CODPROD,)).fetchone()
                if not antigo:
                    raise ValueError('Produto não encontrado.')
                if antigo['CODVOL'] != p.CODVOL and db.execute('SELECT 1 FROM TGFITE WHERE CODPROD=? LIMIT 1',(p.CODPROD,)).fetchone():
                    raise ValueError('A unidade não pode ser alterada: o produto já está vinculado a notas.')
                db.execute('UPDATE TGFPRO SET DESCRPROD=?,CODVOL=?,ESTMIN=?,CODGRUPOPROD=? WHERE CODPROD=?',valores)
            else:
                db.execute('INSERT INTO TGFPRO (DESCRPROD,CODVOL,ESTMIN,CODGRUPOPROD,CODPROD) VALUES (?,?,?,?,?)',valores)

    def consulta(self, filtros):
        with self.conectar() as db:
            rows = [dict(r) for r in db.execute('''SELECT P.*,G.DESCRGRUPOPROD,COALESCE(E.ESTOQUE,0) AS ESTOQUE
                FROM TGFPRO P JOIN TGFGRU G ON G.CODGRUPOPROD=P.CODGRUPOPROD
                LEFT JOIN TGFEST E ON E.CODPROD=P.CODPROD AND E.CODEMP=1 AND E.CODLOCAL=1
                  AND E.CONTROLE=' ' AND E.TIPO='P' AND E.CODPARC=0 ORDER BY P.CODPROD''')]
        termo = normalizar(filtros.get('q','').strip())
        return [r for r in rows if (not termo or termo in normalizar(r['DESCRPROD']) or termo==str(r['CODPROD']))
                and (not filtros.get('grupo') or str(r['CODGRUPOPROD'])==filtros['grupo'])
                and (filtros.get('baixo')!='1' or r['ESTOQUE'] < r['ESTMIN'])]

    def tops(self, portal=None):
        with self.conectar() as db:
            rows=[dict(r) for r in db.execute('''SELECT T.* FROM TGFTOP T WHERE DHALTER=(
                SELECT MAX(X.DHALTER) FROM TGFTOP X WHERE X.CODTIPOPER=T.CODTIPOPER) ORDER BY CODTIPOPER''')]
        tipos = ('C','O') if portal=='compras' else ('V','P') if portal=='vendas' else tuple(TIPOS)
        return [r for r in rows if r['TIPMOV'] in tipos]


class ProdutoService:
    def __init__(self, repository):
        self.repository=repository

    def salvar(self, dados, codigo_edicao=None):
        codigo=inteiro(codigo_edicao if codigo_edicao is not None else dados.get('CODPROD',''),'Código')
        nome=dados.get('DESCRPROD','').strip()
        if not 1 <= len(nome) <= 100:
            raise ValueError('Informe uma descrição de até 100 caracteres.')
        unidade=dados.get('CODVOL','').strip().upper()
        if unidade not in {u['CODVOL'] for u in self.repository.unidades()}:
            raise ValueError('Selecione uma unidade válida.')
        grupo=inteiro(dados.get('CODGRUPOPROD',1),'Grupo')
        if grupo not in {g['CODGRUPOPROD'] for g in self.repository.listar('TGFGRU')}:
            raise ValueError('Selecione um grupo válido.')
        minimo=numero(dados.get('ESTMIN',''),'Estoque mínimo')
        try:
            self.repository.salvar(Produto(codigo,nome,unidade,float(minimo),grupo),codigo_edicao is not None)
        except sqlite3.IntegrityError:
            raise ValueError('Código já cadastrado ou relacionamento inválido.')


class CadastroService:
    def __init__(self, repository):
        self.repository=repository

    def salvar(self, tipo, dados):
        with self.repository.conectar() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                if tipo in ('grupos','parceiros'):
                    tabela,pk,descricao = ('TGFGRU','CODGRUPOPROD','DESCRGRUPOPROD') if tipo=='grupos' else ('TGFPAR','CODPARC','NOMEPARC')
                    codigo=inteiro(dados.get(pk,''),'Código')
                    nome=dados.get(descricao,'').strip()
                    if not 1 <= len(nome) <= 100:
                        raise ValueError('Informe uma descrição de até 100 caracteres.')
                    db.execute(f'INSERT INTO {tabela} ({pk},{descricao}) VALUES (?,?)',(codigo,nome))
                elif tipo=='tops':
                    codigo=inteiro(dados.get('CODTIPOPER',''),'TOP',maximo=99999)
                    nome=dados.get('DESCROPER','').strip()
                    mov=dados.get('TIPMOV','')
                    efeito=dados.get('ATUALEST','')
                    validos={'C':('E','N'),'V':('B','N'),'O':('N',),'P':('N',)}
                    if not nome or len(nome)>100 or efeito not in validos.get(mov,()):
                        raise ValueError('TOP inválida. Compra: Entrada/Não atualiza; Venda: Baixa/Não atualiza; Pedidos: Não atualiza.')
                    db.execute('INSERT INTO TGFTOP VALUES (?,?,?,?,?)',(codigo,datetime.now().isoformat(timespec='microseconds'),nome,mov,efeito))
                else:
                    raise ValueError('Cadastro inválido.')
            except sqlite3.IntegrityError:
                raise ValueError('Código já cadastrado.')


class NotaService:
    def __init__(self, repository):
        self.repository=repository

    def obter(self,nunota):
        with self.repository.conectar() as db:
            cab=db.execute('''SELECT C.*,P.NOMEPARC,T.DESCROPER,T.ATUALEST FROM TGFCAB C
                JOIN TGFPAR P ON P.CODPARC=C.CODPARC JOIN TGFTOP T ON T.CODTIPOPER=C.CODTIPOPER AND T.DHALTER=C.DHTIPOPER
                WHERE C.NUNOTA=?''',(nunota,)).fetchone()
            itens=[dict(r) for r in db.execute('''SELECT I.*,P.DESCRPROD FROM TGFITE I JOIN TGFPRO P ON P.CODPROD=I.CODPROD
                WHERE NUNOTA=? ORDER BY SEQUENCIA''',(nunota,))]
            return (dict(cab),itens) if cab else (None,[])

    def salvar(self,portal,dados,itens,nunota=None):
        tipos=('C','O') if portal=='compras' else ('V','P')
        codigo=inteiro(dados.get('CODTIPOPER',''),'TOP',maximo=99999)
        parceiro=inteiro(dados.get('CODPARC',''),'Parceiro')
        num=inteiro(dados.get('NUMNOTA','0'),'Número da nota',minimo=0)
        dtneg=data_iso(dados.get('DTNEG',''))
        dtmov=data_iso(dados.get('DTMOV',''))
        obs=dados.get('OBSERVACAO','').strip()
        if len(obs)>500:
            raise ValueError('A observação aceita até 500 caracteres.')
        if not 1 <= len(itens) <= 100:
            raise ValueError('Inclua de 1 a 100 itens na nota.')
        with self.repository.conectar() as db:
            db.execute('BEGIN IMMEDIATE')
            antigo=None
            if nunota is not None:
                antigo=db.execute('SELECT * FROM TGFCAB WHERE NUNOTA=?',(nunota,)).fetchone()
                if not antigo or antigo['TIPMOV'] not in tipos or antigo['STATUSNOTA']!='P':
                    raise ValueError('Somente notas pendentes deste portal podem ser editadas.')
            if antigo and antigo['CODTIPOPER']==codigo:
                top=db.execute('SELECT * FROM TGFTOP WHERE CODTIPOPER=? AND DHALTER=?',(codigo,antigo['DHTIPOPER'])).fetchone()
            else:
                top=db.execute('SELECT * FROM TGFTOP WHERE CODTIPOPER=? ORDER BY DHALTER DESC LIMIT 1',(codigo,)).fetchone()
            if not top or top['TIPMOV'] not in tipos:
                raise ValueError('Selecione uma TOP compatível com o portal.')
            if not db.execute('SELECT 1 FROM TGFPAR WHERE CODPARC=?',(parceiro,)).fetchone():
                raise ValueError('Parceiro não encontrado.')
            entidades=[]
            for i in itens:
                prod=inteiro(i.get('CODPROD',''),'Produto')
                p=db.execute('SELECT * FROM TGFPRO WHERE CODPROD=?',(prod,)).fetchone()
                if not p:
                    raise ValueError(f'Produto {prod} não encontrado.')
                entidades.append(ItemNota(prod,p['CODVOL'],numero(i.get('QTDNEG',''),'Quantidade',positivo=True),numero(i.get('VLRUNIT',''),'Valor unitário',casas=2)))
            total=sum((i.total for i in entidades),Decimal(0))
            if total > Decimal('999999999.99'):
                raise ValueError('O total da nota não pode superar R$ 999.999.999,99.')
            valores=(num,parceiro,dtneg,dtmov,codigo,top['DHALTER'],top['TIPMOV'],float(total),obs)
            if nunota is None:
                nunota=db.execute('''INSERT INTO TGFCAB (NUMNOTA,CODPARC,DTNEG,DTMOV,CODTIPOPER,DHTIPOPER,TIPMOV,VLRNOTA,OBSERVACAO)
                    VALUES (?,?,?,?,?,?,?,?,?)''',valores).lastrowid
            else:
                db.execute('''UPDATE TGFCAB SET NUMNOTA=?,CODPARC=?,DTNEG=?,DTMOV=?,CODTIPOPER=?,DHTIPOPER=?,TIPMOV=?,VLRNOTA=?,OBSERVACAO=? WHERE NUNOTA=?''',valores+(nunota,))
                db.execute('DELETE FROM TGFITE WHERE NUNOTA=?',(nunota,))
            for seq,i in enumerate(entidades,1):
                db.execute('''INSERT INTO TGFITE (NUNOTA,SEQUENCIA,CODPROD,CODVOL,QTDNEG,VLRUNIT,VLRTOT) VALUES (?,?,?,?,?,?,?)''',
                           (nunota,seq,i.CODPROD,i.CODVOL,float(i.QTDNEG),float(i.VLRUNIT),float(i.total)))
            return nunota

    def confirmar(self,nunota):
        with self.repository.conectar() as db:
            db.execute('BEGIN IMMEDIATE')
            cab=db.execute('''SELECT C.*,T.ATUALEST FROM TGFCAB C JOIN TGFTOP T ON
                T.CODTIPOPER=C.CODTIPOPER AND T.DHALTER=C.DHTIPOPER WHERE NUNOTA=?''',(nunota,)).fetchone()
            if not cab:
                raise ValueError('Nota não encontrada.')
            if cab['STATUSNOTA']=='L':
                return False
            itens=db.execute('SELECT * FROM TGFITE WHERE NUNOTA=? ORDER BY SEQUENCIA',(nunota,)).fetchall()
            if not itens:
                raise ValueError('Inclua ao menos um item antes de confirmar.')
            for i in itens:
                if cab['ATUALEST']=='N':
                    continue
                chave=(i['CODEMP'],i['CODLOCALORIG'],i['CODPROD'],i['CONTROLE'],'P',0)
                row=db.execute('''SELECT ESTOQUE FROM TGFEST WHERE CODEMP=? AND CODLOCAL=? AND CODPROD=? AND CONTROLE=? AND TIPO=? AND CODPARC=?''',chave).fetchone()
                saldo=Decimal(str(row['ESTOQUE'])) if row else Decimal(0)
                qtd=Decimal(str(i['QTDNEG']))
                novo=saldo+qtd if cab['ATUALEST']=='E' else saldo-qtd
                if novo<0:
                    raise ValueError(f'Saldo insuficiente para o produto {i["CODPROD"]}. Disponível: {saldo}; solicitado: {qtd}. Nenhum item foi movimentado.')
                if novo > Decimal('999999999'):
                    raise ValueError('O saldo do produto ultrapassaria o limite de 999999999.')
                if row:
                    db.execute('''UPDATE TGFEST SET ESTOQUE=? WHERE CODEMP=? AND CODLOCAL=? AND CODPROD=? AND CONTROLE=? AND TIPO=? AND CODPARC=?''',(float(novo),)+chave)
                else:
                    db.execute('INSERT INTO TGFEST (CODEMP,CODLOCAL,CODPROD,CONTROLE,TIPO,CODPARC,ESTOQUE) VALUES (?,?,?,?,?,?,?)',chave+(float(novo),))
            db.execute("UPDATE TGFCAB SET STATUSNOTA='L' WHERE NUNOTA=?",(nunota,))
            return True

    def excluir_pendente(self,nunota):
        with self.repository.conectar() as db:
            db.execute('BEGIN IMMEDIATE')
            r=db.execute("DELETE FROM TGFCAB WHERE NUNOTA=? AND STATUSNOTA='P'",(nunota,))
            if r.rowcount!=1:
                raise ValueError('Somente notas pendentes podem ser excluídas.')

    def excluir(self,nunota):
        """Exclui cabeçalho/itens e desfaz o efeito histórico da TOP atomicamente."""
        with self.repository.conectar() as db:
            db.execute('BEGIN IMMEDIATE')
            cab=db.execute("""SELECT C.*,T.ATUALEST FROM TGFCAB C JOIN TGFTOP T
                ON T.CODTIPOPER=C.CODTIPOPER AND T.DHALTER=C.DHTIPOPER
                WHERE NUNOTA=?""",(nunota,)).fetchone()
            if not cab:
                raise ValueError('Nota não encontrada.')
            if cab['STATUSNOTA']=='L' and cab['ATUALEST'] in ('E','B'):
                itens=db.execute('SELECT * FROM TGFITE WHERE NUNOTA=?',(nunota,)).fetchall()
                for i in itens:
                    chave=(i['CODEMP'],i['CODLOCALORIG'],i['CODPROD'],i['CONTROLE'],'P',0)
                    row=db.execute("""SELECT ESTOQUE FROM TGFEST WHERE CODEMP=? AND CODLOCAL=?
                        AND CODPROD=? AND CONTROLE=? AND TIPO=? AND CODPARC=?""",chave).fetchone()
                    saldo=Decimal(str(row['ESTOQUE'])) if row else Decimal(0)
                    quantidade=Decimal(str(i['QTDNEG']))
                    novo=saldo-quantidade if cab['ATUALEST']=='E' else saldo+quantidade
                    if novo<0:
                        raise ValueError(f'Não é possível excluir: o produto {i["CODPROD"]} ficaria com saldo negativo. Revise as saídas vinculadas ao estoque antes de excluir esta entrada.')
                    if novo>Decimal('999999999'):
                        raise ValueError('A reversão ultrapassaria o limite de saldo.')
                    db.execute("""INSERT INTO TGFEST (CODEMP,CODLOCAL,CODPROD,CONTROLE,TIPO,CODPARC,ESTOQUE)
                        VALUES (?,?,?,?,?,?,?) ON CONFLICT(CODEMP,CODLOCAL,CODPROD,CONTROLE,TIPO,CODPARC)
                        DO UPDATE SET ESTOQUE=excluded.ESTOQUE""",chave+(float(novo),))
            db.execute('DELETE FROM TGFCAB WHERE NUNOTA=?',(nunota,))

    def listar(self,portal,filtros):
        inicio,fim=periodo(filtros)
        tipos=('C','O') if portal=='compras' else ('V','P')
        where=['C.TIPMOV IN (?,?)']; args=list(tipos)
        for campo,chave in [('C.STATUSNOTA','status'),('C.TIPMOV','tipmov'),('C.CODTIPOPER','top'),('C.CODPARC','parceiro')]:
            if filtros.get(chave):
                where.append(campo+'=?');args.append(filtros[chave])
        if inicio: where.append('C.DTMOV>=?');args.append(inicio)
        if fim: where.append('C.DTMOV<=?');args.append(fim)
        if filtros.get('produto'):
            where.append('EXISTS(SELECT 1 FROM TGFITE I WHERE I.NUNOTA=C.NUNOTA AND I.CODPROD=?)');args.append(filtros['produto'])
        if filtros.get('q','').strip():
            where.append('(CAST(C.NUNOTA AS TEXT)=? OR CAST(C.NUMNOTA AS TEXT)=? OR instr(NORMALIZAR(P.NOMEPARC),NORMALIZAR(?))>0)')
            args.extend([filtros['q'].strip()]*3)
        with self.repository.conectar() as db:
            return [dict(r) for r in db.execute('''SELECT C.*,P.NOMEPARC,T.DESCROPER,T.ATUALEST FROM TGFCAB C
                JOIN TGFPAR P ON P.CODPARC=C.CODPARC JOIN TGFTOP T ON T.CODTIPOPER=C.CODTIPOPER AND T.DHALTER=C.DHTIPOPER
                WHERE '''+' AND '.join(where)+' ORDER BY C.DTMOV DESC,C.NUNOTA DESC',args)]

    def extrato(self,filtros):
        inicio,fim=periodo(filtros)
        with self.repository.conectar() as db:
            rows=db.execute('''SELECT C.NUNOTA,C.NUMNOTA,C.DTMOV,C.TIPMOV,C.CODTIPOPER,P.CODGRUPOPROD,
                G.DESCRGRUPOPROD,I.SEQUENCIA,I.CODPROD,P.DESCRPROD,I.CODVOL,I.QTDNEG,T.ATUALEST
                FROM TGFCAB C JOIN TGFITE I ON I.NUNOTA=C.NUNOTA JOIN TGFPRO P ON P.CODPROD=I.CODPROD
                JOIN TGFGRU G ON G.CODGRUPOPROD=P.CODGRUPOPROD JOIN TGFTOP T ON T.CODTIPOPER=C.CODTIPOPER AND T.DHALTER=C.DHTIPOPER
                WHERE C.STATUSNOTA='L' AND T.ATUALEST IN ('E','B') ORDER BY C.DTMOV,C.NUNOTA,I.SEQUENCIA''').fetchall()
        saldos={}; resultado=[]
        for row in rows:
            r=dict(row); codigo=r['CODPROD']; qtd=Decimal(str(r['QTDNEG']))
            r['ANTERIOR']=saldos.get(codigo,Decimal(0))
            saldos[codigo]=r['ANTERIOR']+(qtd if r['ATUALEST']=='E' else -qtd)
            r['SALDO']=saldos[codigo]
            if inicio and r['DTMOV']<inicio or fim and r['DTMOV']>fim: continue
            if any(filtros.get(k) and str(r[c])!=filtros[k] for k,c in [('produto','CODPROD'),('grupo','CODGRUPOPROD'),('tipmov','TIPMOV'),('top','CODTIPOPER')]): continue
            resultado.append(r)
        return resultado


class GerenciamentoService:
    def __init__(self,repository):
        self.repository=repository

    def excluir(self,tipo,codigo):
        tabelas={'produtos':('TGFPRO','CODPROD'),'grupos':('TGFGRU','CODGRUPOPROD'),
                 'parceiros':('TGFPAR','CODPARC'),'tops':('TGFTOP','CODTIPOPER')}
        if tipo not in tabelas:
            raise ValueError('Cadastro inválido.')
        if tipo=='parceiros' and codigo==0:
            raise ValueError('O parceiro 0 representa o estoque próprio e é reservado pelo sistema.')
        tabela,pk=tabelas[tipo]
        with self.repository.conectar() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute(f'SELECT 1 FROM {tabela} WHERE {pk}=?',(codigo,)).fetchone():
                raise ValueError('Registro não encontrado.')
            if tipo=='produtos':
                if db.execute('SELECT 1 FROM TGFITE WHERE CODPROD=?',(codigo,)).fetchone():
                    raise ValueError('Produto utilizado em notas. Exclua primeiro as notas que contêm este produto.')
                if db.execute('SELECT 1 FROM TGFEST WHERE CODPROD=? AND (ESTOQUE<>0 OR RESERVADO<>0)',(codigo,)).fetchone():
                    raise ValueError('Produto com saldo ou reserva não pode ser excluído.')
                db.execute('DELETE FROM TGFEST WHERE CODPROD=?',(codigo,))
            try:
                db.execute(f'DELETE FROM {tabela} WHERE {pk}=?',(codigo,))
            except sqlite3.IntegrityError:
                raise ValueError('Registro em uso. Remova ou altere os vínculos em produtos e notas antes de excluir.')
