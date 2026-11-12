"""Consultas isoladas, somente leitura, no banco SQLite da aplicação."""
import sqlite3
import time
from pathlib import Path
from contextlib import closing


class DatabaseExplorer:
    def __init__(self,caminho):
        self.caminho=Path(caminho).resolve()

    def conectar(self):
        db=sqlite3.connect(self.caminho.as_uri()+'?mode=ro',uri=True,timeout=2)
        db.execute('PRAGMA query_only=ON')
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,1000000)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH,20000)
        return db

    def tabelas(self):
        with closing(self.conectar()) as db:
            return [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    def colunas(self,tabela):
        if tabela not in self.tabelas():
            raise ValueError('Tabela inválida.')
        with closing(self.conectar()) as db:
            return db.execute('PRAGMA table_info("'+tabela.replace('"','""')+'")').fetchall()

    def consultar(self,sql):
        if not sql.strip() or len(sql)>20000:
            raise ValueError('Informe uma consulta de até 20.000 caracteres.')
        inicio=time.monotonic()
        permitidos={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_RECURSIVE}
        funcoes={'abs','avg','count','sum','total','min','max','round','coalesce','ifnull','nullif',
                 'lower','upper','length','substr','substring','trim','ltrim','rtrim','replace',
                 'instr','like','glob','date','time','datetime','strftime','julianday','unixepoch',
                 'typeof','printf','format','group_concat','row_number','rank','dense_rank','lag','lead'}
        def autorizar(acao,arg1,arg2,banco,origem):
            if acao in permitidos: return sqlite3.SQLITE_OK
            if acao==sqlite3.SQLITE_FUNCTION and (arg2 or '').lower() in funcoes:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        try:
            with closing(self.conectar()) as db:
                db.set_authorizer(autorizar)
                db.set_progress_handler(lambda: int(time.monotonic()-inicio>2),1000)
                cursor=db.execute(sql)
                if cursor.description is None:
                    raise ValueError('Somente consultas SELECT ou WITH de leitura são permitidas.')
                rows=cursor.fetchmany(501)
                return dict(colunas=[c[0] for c in cursor.description],linhas=rows[:500],
                            limitado=len(rows)>500,ms=round((time.monotonic()-inicio)*1000,1))
        except sqlite3.Error as exc:
            raise ValueError('Consulta não executada: '+str(exc)+'. Somente leitura; limite de 2 segundos e 500 linhas.') from exc
