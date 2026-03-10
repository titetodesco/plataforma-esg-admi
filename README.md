URL da aplicação https://plataforma-esg-admi1.streamlit.app/

## Execução local (Windows/Linux/macOS)

1. Instale as dependências:
	- `pip install -r requirements.txt`
2. Rode a aplicação:
	- `streamlit run app.py`

### Banco de dados

- **Turso obrigatório:** defina `TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN` (em variáveis de ambiente ou `st.secrets`).
- Sem essas credenciais, a aplicação não inicia.

### Deploy no Streamlit Cloud (com Turso)

1. No app do Streamlit Cloud, vá em **Settings → Secrets**.
2. Adicione:

```toml
TURSO_DATABASE_URL = "libsql://SEU-BANCO.turso.io"
TURSO_AUTH_TOKEN = "SEU_TOKEN"
```

Também é aceito o formato em seção:

```toml
[turso]
database_url = "libsql://SEU-BANCO.turso.io"
auth_token = "SEU_TOKEN"
```

3. Faça o deploy/redeploy.

Com esses secrets, a aplicação conecta no Turso. Sem secrets válidos, a aplicação falha na inicialização (com mensagem explícita).


Sobre o Layout planilha parametrização ESG que você me ajudou a elaborar, eu fiz algumas alterações e pensei em implementar uma aplicação simples em python, usando o github e streamlit para fazer a gestão de uma planilha completa com todos os indicadores, seguindo a taxonomia
Eixo: Ambiental (E), Social (S) e Governança (G)
	Tema
		Tópico
			Indicador
				Variável
O indicador é composto por uma ou mais variáveis e pode ter uma fórmula de cálculo. As variáveis podem ser do tipo numérica, sim/não ou múltipla escolha (likert 5 pontos). O indicador pode ter um tipo (Pressão, Estado, ...) e o Tema pode ser dentro de um tópico (Redução, Resposta, ...). Essa definição completa será chamada de macro-base. A partir da macro-base, deve ser gerada uma nova planilha com informações do setor, porte e região do país para o setup de um questionário, onde serão selecionados os temas que farão parte do questionário, bem como escolher os tópicos e os indicadores. Posteriormente, para cada indicador escolhido, deve ser definido os valores de referência para que todas as respostas possam estar compreendidas em 5 valores, de 1 a 5, estabelecendo o nível de maturidade do indicador. Além disso, deve ser estabelecido o peso de cada indicador que serão agregados para o Tópico e Tema. Da mesma forma, deve-se também atribuir pesos para os temas, pois os temas serão agregados aos eixos finalizando com nível de maturidade em cada eixo. Vamos iniciar com esse escopo e por meio de interações vamos evoluindo. Você entendeu o que desejo ou ficou muito confuso? Sintetizando, a partir da construção da macro-base (devo implementar uma interface para preencher a planilha da macro-base) implementar uma interface para gerar uma nova planilha que será usada para configura um questionário que será respondido por organizações do setor, porte e região definidos no questionário.
