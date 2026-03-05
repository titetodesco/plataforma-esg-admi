PRAGMA foreign_keys = ON;

-- ===== MACRO-BASE =====

CREATE TABLE IF NOT EXISTS eixo (
  eixo_id       TEXT PRIMARY KEY,
  codigo        TEXT NOT NULL UNIQUE,
  nome          TEXT NOT NULL,
  descricao     TEXT,
  peso_default  INTEGER NOT NULL DEFAULT 1 CHECK (peso_default BETWEEN 1 AND 10)
);

CREATE TABLE IF NOT EXISTS tema (
  tema_id       TEXT PRIMARY KEY,
  eixo_id       TEXT NOT NULL,
  codigo        TEXT,
  nome          TEXT NOT NULL,
  descricao     TEXT,
  peso_default  INTEGER NOT NULL DEFAULT 1 CHECK (peso_default BETWEEN 1 AND 10),
  FOREIGN KEY (eixo_id) REFERENCES eixo(eixo_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  UNIQUE (eixo_id, codigo)
);

CREATE TABLE IF NOT EXISTS topico (
  topico_id     TEXT PRIMARY KEY,
  tema_id       TEXT NOT NULL,
  codigo        TEXT,
  nome          TEXT NOT NULL,
  descricao     TEXT,
  peso_default  INTEGER NOT NULL DEFAULT 1 CHECK (peso_default BETWEEN 1 AND 10),
  FOREIGN KEY (tema_id) REFERENCES tema(tema_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  UNIQUE (tema_id, codigo)
);

CREATE TABLE IF NOT EXISTS indicador (
  indicador_id      TEXT PRIMARY KEY,
  topico_id         TEXT NOT NULL,
  codigo            TEXT,
  nome              TEXT NOT NULL,
  descricao         TEXT,
  tipo_indicador    TEXT NOT NULL CHECK (tipo_indicador IN ('DIRETO','CALCULADO')),
  psr_tipo          TEXT CHECK (psr_tipo IN ('PRESSAO','ESTADO','RESPOSTA')),
  formula           TEXT,          -- ex.: (VAR_V2 - VAR_V1) / VAR_V2
  unidade_resultado TEXT,
  peso_default      INTEGER NOT NULL DEFAULT 1 CHECK (peso_default BETWEEN 1 AND 10),
  FOREIGN KEY (topico_id) REFERENCES topico(topico_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  UNIQUE (topico_id, codigo)
);

CREATE TABLE IF NOT EXISTS variavel (
  variavel_id     TEXT PRIMARY KEY,
  codigo          TEXT UNIQUE,
  pergunta_texto  TEXT NOT NULL,
  descricao       TEXT,
  tipo_resposta   TEXT NOT NULL CHECK (tipo_resposta IN ('MULTIPLA_5','SIM_NAO','SIM_IMPLANTACAO_NAO','NUMERICA')),
  unidade_entrada TEXT,
  observacoes     TEXT
);

CREATE TABLE IF NOT EXISTS variavel_opcao (
  variavel_id   TEXT NOT NULL,
  ordem         INTEGER NOT NULL CHECK (ordem >= 1 AND ordem <= 5),
  texto_opcao   TEXT NOT NULL,
  score_1a5     INTEGER NOT NULL CHECK (score_1a5 BETWEEN 1 AND 5),
  PRIMARY KEY (variavel_id, ordem),
  FOREIGN KEY (variavel_id) REFERENCES variavel(variavel_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS indicador_variavel (
  indicador_id   TEXT NOT NULL,
  variavel_id    TEXT NOT NULL,
  papel          TEXT NOT NULL DEFAULT 'ENTRADA' CHECK (papel IN ('ENTRADA','AUXILIAR')),
  obrigatoria    INTEGER NOT NULL DEFAULT 1 CHECK (obrigatoria IN (0,1)),
  peso           INTEGER CHECK (peso BETWEEN 1 AND 10),  -- opcional
  PRIMARY KEY (indicador_id, variavel_id),
  FOREIGN KEY (indicador_id) REFERENCES indicador(indicador_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (variavel_id) REFERENCES variavel(variavel_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ===== SETUP =====

CREATE TABLE IF NOT EXISTS questionario (
  questionario_id TEXT PRIMARY KEY,
  setor           TEXT,
  porte           TEXT,
  regiao          TEXT,
  versao          TEXT,
  status          TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED')),
  created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  observacao      TEXT
);

CREATE TABLE IF NOT EXISTS indicador_config (
  questionario_id TEXT NOT NULL,
  indicador_id    TEXT NOT NULL,
  ativo           INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
  peso_indicador  INTEGER NOT NULL DEFAULT 1 CHECK (peso_indicador BETWEEN 1 AND 10),
  PRIMARY KEY (questionario_id, indicador_id),
  FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (indicador_id) REFERENCES indicador(indicador_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS peso_tema (
  questionario_id TEXT NOT NULL,
  tema_id         TEXT NOT NULL,
  peso_tema       INTEGER NOT NULL DEFAULT 1 CHECK (peso_tema BETWEEN 1 AND 10),
  PRIMARY KEY (questionario_id, tema_id),
  FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (tema_id) REFERENCES tema(tema_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS peso_topico (
  questionario_id TEXT NOT NULL,
  topico_id       TEXT NOT NULL,
  peso_topico     INTEGER NOT NULL DEFAULT 1 CHECK (peso_topico BETWEEN 1 AND 10),
  PRIMARY KEY (questionario_id, topico_id),
  FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (topico_id) REFERENCES topico(topico_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS faixa_referencia (
  questionario_id TEXT NOT NULL,
  indicador_id    TEXT NOT NULL,
  nivel           INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 5),
  tipo_regra      TEXT NOT NULL CHECK (tipo_regra IN ('INTERVALO','EXATO','DIRETO')),
  valor_min       REAL,
  valor_max       REAL,
  valor_exato     REAL,
  rotulo          TEXT,
  PRIMARY KEY (questionario_id, indicador_id, nivel),
  FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (indicador_id) REFERENCES indicador(indicador_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recomendacao_tema (
  questionario_id TEXT NOT NULL,
  tema_id         TEXT NOT NULL,
  nivel           INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 5),
  recomendacao    TEXT NOT NULL,
  PRIMARY KEY (questionario_id, tema_id, nivel),
  FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (tema_id) REFERENCES tema(tema_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recomendacao_eixo (
  questionario_id TEXT NOT NULL,
  eixo_id         TEXT NOT NULL,
  nivel           INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 5),
  recomendacao    TEXT NOT NULL,
  PRIMARY KEY (questionario_id, eixo_id, nivel),
  FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (eixo_id) REFERENCES eixo(eixo_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recomendacao_tema_default (
  tema_id      TEXT NOT NULL,
  nivel        INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 5),
  recomendacao TEXT NOT NULL,
  PRIMARY KEY (tema_id, nivel),
  FOREIGN KEY (tema_id) REFERENCES tema(tema_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recomendacao_eixo_default (
  eixo_id      TEXT NOT NULL,
  nivel        INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 5),
  recomendacao TEXT NOT NULL,
  PRIMARY KEY (eixo_id, nivel),
  FOREIGN KEY (eixo_id) REFERENCES eixo(eixo_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS ix_tema_eixo    ON tema(eixo_id);
CREATE INDEX IF NOT EXISTS ix_topico_tema  ON topico(tema_id);
CREATE INDEX IF NOT EXISTS ix_ind_topico   ON indicador(topico_id);
CREATE INDEX IF NOT EXISTS ix_indcfg_qst   ON indicador_config(questionario_id);
CREATE INDEX IF NOT EXISTS ix_faixa_qst    ON faixa_referencia(questionario_id);
