"""Interface web local do Estoque Fácil."""
import os
import secrets
from pathlib import Path
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from explorer import DatabaseExplorer
from domain import ProdutoRepository, ProdutoService, NotaService, CadastroService, GerenciamentoService, TIPOS, EFEITOS


def create_app(database=None):
    app=Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),MAX_CONTENT_LENGTH=262144,
                      SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_HTTPONLY=True)
    caminho=Path(database) if database else Path(__file__).parent/'instance'/'estoque.db'
    caminho.parent.mkdir(parents=True,exist_ok=True)
    repo=ProdutoRepository(str(caminho));repo.inicializar()
    produtos=ProdutoService(repo);notas=NotaService(repo);cadastros=CadastroService(repo)

    @app.before_request
    def proteger_formularios():
        if 'csrf' not in session: session['csrf']=secrets.token_hex(32)
        if request.method=='POST' and not secrets.compare_digest(request.form.get('csrf',''),session['csrf']):
            abort(400,description='Formulário expirado. Atualize a página e tente novamente.')

    @app.context_processor
    def contexto():
        return dict(tipos=TIPOS,efeitos=EFEITOS,hoje=date.today().isoformat())

    @app.template_filter('qtd')
    def qtd(valor):
        return f'{float(valor):.3f}'.rstrip('0').rstrip('.').replace('.',',')

    @app.template_filter('moeda')
    def moeda(valor):
        return f'{float(valor):,.2f}'.replace(',','_').replace('.',',').replace('_','.')

    @app.template_filter('data')
    def data(valor):
        return str(valor)[:10][8:10]+'/'+str(valor)[5:7]+'/'+str(valor)[:4]

    @app.get('/')
    @app.get('/produtos')
    def index():
        termo=request.args.get('q','').strip()
        return render_template('index.html',produtos=repo.buscar(termo),termo=termo,active='produtos',title='Produtos')

    @app.route('/produtos/novo',methods=['GET','POST'])
    @app.route('/produtos/<int:codigo>/editar',methods=['GET','POST'])
    def formulario(codigo=None):
        produto=repo.obter(codigo) if codigo is not None else {}
        if codigo is not None and produto is None: abort(404)
        erro=None
        if request.method=='POST':
            produto=request.form.to_dict()
            if codigo is not None: produto['CODPROD']=codigo
            try:
                produtos.salvar(produto,codigo)
                flash('Produto atualizado com sucesso.' if codigo is not None else 'Produto cadastrado com sucesso.')
                return redirect(url_for('index'))
            except ValueError as exc: erro=str(exc)
        return render_template('form.html',produto=produto,editar=codigo is not None,unidades=repo.unidades(),
                               grupos=repo.listar('TGFGRU'),erro=erro,active='produtos',title='Produto'),422 if erro else 200

    @app.get('/consulta-produtos')
    def consulta():
        filtros=request.args.to_dict()
        return render_template('consulta.html',produtos=repo.consulta(filtros),f=filtros,grupos=repo.listar('TGFGRU'),
                               active='consulta',title='Consulta de Produtos')

    def validar_portal(portal):
        if portal not in ('compras','vendas'): abort(404)

    @app.get('/portal/<portal>')
    def portal(portal):
        validar_portal(portal);f=request.args.to_dict();erro=None
        try: rows=notas.listar(portal,f)
        except ValueError as exc: rows=[];erro=str(exc)
        return render_template('portal.html',portal=portal,notas=rows,f=f,erro=erro,tops=repo.tops(portal),
                               produtos=repo.buscar(),parceiros=repo.listar('TGFPAR'),active=portal,title='Portal de '+portal.capitalize()),422 if erro else 200

    @app.route('/portal/<portal>/nova',methods=['GET','POST'])
    @app.route('/portal/<portal>/<int:nunota>/editar',methods=['GET','POST'])
    def nota_form(portal,nunota=None):
        validar_portal(portal);cab,itens=notas.obter(nunota) if nunota else ({},[])
        if nunota and (not cab or cab['TIPMOV'] not in (('C','O') if portal=='compras' else ('V','P'))): abort(404)
        if nunota and cab['STATUSNOTA']!='P': abort(409,description='Nota confirmada não pode ser editada.')
        erro=None
        if request.method=='POST':
            cab=request.form.to_dict()
            if nunota: cab['NUNOTA']=nunota
            codigos=request.form.getlist('CODPROD');quantidades=request.form.getlist('QTDNEG');valores=request.form.getlist('VLRUNIT')
            itens=[dict(CODPROD=c,QTDNEG=quantidades[i] if i<len(quantidades) else '',VLRUNIT=valores[i] if i<len(valores) else '') for i,c in enumerate(codigos)]
            try:
                nunota=notas.salvar(portal,cab,itens,nunota)
                flash('Nota salva como pendente. Confira os itens e confirme para aplicar a TOP.')
                return redirect(url_for('nota',nunota=nunota))
            except ValueError as exc: erro=str(exc)
        tops=repo.tops(portal)
        if nunota:
            original,_=notas.obter(nunota)
            # Ao manter a TOP, a edição preserva a versão da nota, mesmo que já haja outra versão.
            for t in tops:
                if t['CODTIPOPER']==original['CODTIPOPER']:
                    t.update(DESCROPER=original['DESCROPER']+' (versão da nota)',TIPMOV=original['TIPMOV'],ATUALEST=original['ATUALEST'])
            if not any(t['CODTIPOPER']==original['CODTIPOPER'] for t in tops):
                tops.append(dict(CODTIPOPER=original['CODTIPOPER'],DESCROPER=original['DESCROPER']+' (versão da nota)',TIPMOV=original['TIPMOV'],ATUALEST=original['ATUALEST']))
        return render_template('nota_form.html',cab=cab,itens=itens or [{}],portal=portal,tops=tops,
                               produtos=repo.buscar(),parceiros=repo.listar('TGFPAR'),erro=erro,active=portal,title='Lançamento de nota'),422 if erro else 200

    @app.get('/notas/<int:nunota>')
    def nota(nunota):
        cab,itens=notas.obter(nunota)
        if not cab: abort(404)
        portal='compras' if cab['TIPMOV'] in ('C','O') else 'vendas'
        return render_template('nota.html',cab=cab,itens=itens,portal=portal,active=portal,title=f'Nota {nunota}')

    @app.post('/notas/<int:nunota>/confirmar')
    def confirmar(nunota):
        try:
            ok=notas.confirmar(nunota)
            flash('Nota confirmada. Efeito da TOP aplicado.' if ok else 'Esta nota já estava confirmada; o estoque não foi movimentado novamente.')
        except ValueError as exc: flash(str(exc),'erro')
        return redirect(url_for('nota',nunota=nunota))

    @app.post('/notas/<int:nunota>/excluir')
    def excluir(nunota):
        cab,_=notas.obter(nunota)
        if not cab: abort(404)
        try:
            notas.excluir(nunota);flash('Nota e itens excluídos. O efeito no estoque, quando existente, foi revertido.')
        except ValueError as exc:
            flash(str(exc),'erro');return redirect(url_for('nota',nunota=nunota))
        return redirect(url_for('portal',portal='compras' if cab['TIPMOV'] in ('C','O') else 'vendas'))

    @app.route('/grupos',methods=['GET','POST'])
    def grupos():
        f=request.args.to_dict();aba=f.get('aba','extrato');erro=None
        if request.method=='POST':
            aba='cadastro'
            try:
                cadastros.salvar('grupos',request.form);flash('Grupo cadastrado.')
                return redirect(url_for('grupos',aba='cadastro'))
            except ValueError as exc: erro=str(exc)
        try: rows=notas.extrato(f)
        except ValueError as exc: rows=[];erro=str(exc)
        return render_template('grupos.html',aba=aba,rows=rows,f=f,erro=erro,grupos=repo.listar('TGFGRU'),
                               produtos=repo.buscar(),tops=repo.tops(),active='grupos',title='Gerência de Grupos de Produtos'),422 if erro else 200

    @app.route('/cadastros/<tipo>',methods=['GET','POST'])
    def cadastro(tipo):
        if tipo not in ('parceiros','tops'): abort(404)
        erro=None
        if request.method=='POST':
            try:
                cadastros.salvar(tipo,request.form);flash('Nova versão da TOP salva.' if tipo=='tops' else 'Parceiro cadastrado.')
                return redirect(url_for('cadastro',tipo=tipo))
            except ValueError as exc: erro=str(exc)
        return render_template('cadastro.html',tipo=tipo,rows=repo.tops() if tipo=='tops' else repo.listar('TGFPAR'),
                               erro=erro,active=tipo,title='Tipos de Operação' if tipo=='tops' else 'Parceiros'),422 if erro else 200

    @app.post('/gerenciar/<tipo>/<int:codigo>/excluir')
    def excluir_cadastro(tipo,codigo):
        if tipo not in ('produtos','grupos','parceiros','tops'): abort(404)
        try:
            GerenciamentoService(repo).excluir(tipo,codigo)
            flash('Registro excluído.')
        except ValueError as exc: flash(str(exc),'erro')
        destino=url_for('index') if tipo=='produtos' else url_for('grupos',aba='cadastro') if tipo=='grupos' else url_for('cadastro',tipo=tipo)
        return redirect(destino)

    @app.route('/dbexplorer',methods=['GET','POST'])
    def dbexplorer():
        explorer=DatabaseExplorer(caminho)
        tabelas=explorer.tabelas()
        tabela=request.values.get('tabela','TGFPRO')
        if tabela not in tabelas: abort(400,description='Tabela inválida.')
        sql=request.form.get('sql',f'SELECT * FROM "{tabela}" LIMIT 100;')
        resultado=None;erro=None
        try: resultado=explorer.consultar(sql)
        except ValueError as exc: erro=str(exc)
        return render_template('explorer.html',active='dbexplorer',title='DBExplorer',tabelas=tabelas,
            tabela=tabela,sql=sql,resultado=resultado,colunas=explorer.colunas(tabela),erro=erro),422 if erro else 200

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(413)
    def erro_http(error):
        return render_template('erro.html',erro=error.description,title='Não foi possível continuar'),error.code

    return app


if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=int(os.environ.get('PORT',5000)),debug=False)
