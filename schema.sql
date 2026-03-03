-- schema.sql (SQLite / Turso)
-- Observação: no SQLite, tipos como VARCHAR viram afinidade TEXT, então usamos TEXT/REAL/INTEGER.

PRAGMA foreign_keys = ON;

-- =========================
-- MACRO-BASE
-- =========================

CREATE TABLE IF NOT EXISTS eixo (
    eixo_id     TEXT PRIMARY KEY,        -- ex.: "E", "S", "G"
    codigo      TEXT NOT NULL UNIQUE,     -- ex.: "E"
    nome        TEXT NOT NULL,            -- ex.: "Ambiental"
    descricao   TEXT,
    peso_default REAL CHECK (peso_default >= 0 AND peso_default <= 100)
);

CREATE TABLE IF NOT EXISTS tema (
    tema_id     TEXT PRIMARY KEY,         -- ex.: "E_AGUA"
    eixo_id     TEXT NOT NULL,
    codigo      TEXT,                     -- opcional
    nome        TEXT NOT NULL,
    descricao   TEXT,
    peso_default REAL CHECK (peso_default >= 0 AND peso_default <= 100),

    FOREIGN KEY (eixo_id) REFERENCES eixo(eixo_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (eixo_id, codigo)
);

CREATE TABLE IF NOT EXISTS topico (
    topico_id   TEXT PRIMARY KEY,         -- ex.: "E_AGUA_DEFAULT" ou "E_AGUA_MON"
    tema_id     TEXT NOT NULL,
    codigo      TEXT,                     -- opcional
    nome        TEXT NOT NULL,
    descricao   TEXT,
    is_default  INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0,1)),

    FOREIGN KEY (tema_id) REFERENCES tema(tema_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (tema_id, codigo)
);

-- Garante no máximo 1 tópico default por tema (is_default=1).
-- Índice parcial é suportado no SQLite.
CREATE UNIQUE INDEX IF NOT EXISTS ux_topico_default_por_tema
ON topico(tema_id)
WHERE is_default = 1;

CREATE TABLE IF NOT EXISTS indicador (
    indicador_id     TEXT PRIMARY KEY,    -- ex.: "IND_E_AGUA_01"
    topico_id        TEXT NOT NULL,
    codigo           TEXT,                -- opcional
    nome             TEXT NOT NULL,
    descricao        TEXT,
    unidade          TEXT,                -- ex.: "%", "N/A"
    tipo_resposta    TEXT NOT NULL CHECK (tipo_resposta IN ('MULTIPLA','SIM/NAO','NUMERICA','PERCENTUAL')),
    tipo_indicador   TEXT NOT NULL DEFAULT 'SIMPLES' CHECK (tipo_indicador IN ('SIMPLES','CALCULADO')),
    formula          TEXT,
    peso_default     REAL CHECK (peso_default >= 0 AND peso_default <= 100),

    FOREIGN KEY (topico_id) REFERENCES topico(topico_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    UNIQUE (topico_id, codigo)
);

CREATE TABLE IF NOT EXISTS variavel (
    variavel_id   TEXT PRIMARY KEY,       -- ex.: "VAR_GEE_INVENT"
    codigo        TEXT,
    nome          TEXT NOT NULL,
    descricao     TEXT,
    unidade       TEXT,
    tipo_dado     TEXT NOT NULL DEFAULT 'TEXTO'
        CHECK (tipo_dado IN ('TEXTO','NUMERO','BOOLEAN','DATA','JSON')),
    tipo_resposta TEXT NOT NULL DEFAULT 'TEXTO'
        CHECK (tipo_resposta IN ('MULTIPLA','SIM/NAO','NUMERICA','PERCENTUAL','TEXTO')),
    opcoes_json   TEXT,                   -- JSON opcional p/ MULTIPLA (ex.: ["A","B","C"])
    valor_ref_min REAL,
    valor_ref_max REAL,

    UNIQUE (codigo)
);

CREATE TABLE IF NOT EXISTS indicador_variavel (
    indicador_id  TEXT NOT NULL,
    variavel_id   TEXT NOT NULL,
    papel         TEXT DEFAULT 'ENTRADA' CHECK (papel IN ('ENTRADA','AUXILIAR','SAIDA')),
    obrigatoria   INTEGER NOT NULL DEFAULT 0 CHECK (obrigatoria IN (0,1)),

    PRIMARY KEY (indicador_id, variavel_id),

    FOREIGN KEY (indicador_id) REFERENCES indicador(indicador_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (variavel_id) REFERENCES variavel(variavel_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- =========================
-- SETUP DO QUESTIONÁRIO
-- =========================

CREATE TABLE IF NOT EXISTS questionario (
    questionario_id TEXT PRIMARY KEY,     -- ex.: "QST_2026_001" ou UUID curto
    setor           TEXT,
    porte           TEXT,
    regiao          TEXT,
    versao          TEXT,                 -- ex.: "v1.0"
    status          TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    observacao      TEXT
);

-- Peso por eixo (permite variar por questionário)
CREATE TABLE IF NOT EXISTS peso_eixo (
    questionario_id TEXT NOT NULL,
    eixo_id         TEXT NOT NULL,
    peso_eixo       REAL NOT NULL CHECK (peso_eixo >= 0 AND peso_eixo <= 100),
    PRIMARY KEY (questionario_id, eixo_id),

    FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (eixo_id) REFERENCES eixo(eixo_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS peso_tema (
    questionario_id TEXT NOT NULL,
    tema_id         TEXT NOT NULL,
    peso_tema       REAL NOT NULL CHECK (peso_tema >= 0 AND peso_tema <= 100),
    PRIMARY KEY (questionario_id, tema_id),

    FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (tema_id) REFERENCES tema(tema_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS peso_topico (
    questionario_id TEXT NOT NULL,
    topico_id       TEXT NOT NULL,
    peso_topico     REAL NOT NULL CHECK (peso_topico >= 0 AND peso_topico <= 100),
    PRIMARY KEY (questionario_id, topico_id),

    FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (topico_id) REFERENCES topico(topico_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS indicador_config (
    questionario_id  TEXT NOT NULL,
    indicador_id     TEXT NOT NULL,
    peso_indicador   REAL NOT NULL CHECK (peso_indicador >= 0 AND peso_indicador <= 100),
    ativo            INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0,1)),
    PRIMARY KEY (questionario_id, indicador_id),

    FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (indicador_id) REFERENCES indicador(indicador_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- Faixas/regras de referência para mapear respostas/valores para nível 1..5
CREATE TABLE IF NOT EXISTS faixa_referencia (
    questionario_id TEXT NOT NULL,
    indicador_id    TEXT NOT NULL,
    nivel           INTEGER NOT NULL CHECK (nivel BETWEEN 1 AND 5),
    tipo_regra      TEXT NOT NULL CHECK (tipo_regra IN ('INTERVALO','EXATO','DIRETO')),
    valor_min       REAL,
    valor_max       REAL,
    valor_exato     REAL,
    rotulo          TEXT,
    pontos          REAL,                 -- opcional: 0..100 ou outra escala

    PRIMARY KEY (questionario_id, indicador_id, nivel),

    FOREIGN KEY (questionario_id) REFERENCES questionario(questionario_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (indicador_id) REFERENCES indicador(indicador_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- Índices úteis
CREATE INDEX IF NOT EXISTS ix_tema_eixo       ON tema(eixo_id);
CREATE INDEX IF NOT EXISTS ix_topico_tema     ON topico(tema_id);
CREATE INDEX IF NOT EXISTS ix_indicador_topico ON indicador(topico_id);
CREATE INDEX IF NOT EXISTS ix_indcfg_qst      ON indicador_config(questionario_id);
