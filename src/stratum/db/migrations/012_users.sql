CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR PRIMARY KEY,
    email           VARCHAR UNIQUE NOT NULL,
    username        VARCHAR UNIQUE NOT NULL,
    password_hash   VARCHAR NOT NULL,
    corpus_id       VARCHAR UNIQUE NOT NULL,
    email_verified  BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    is_suspended    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at   TIMESTAMP,
    meta_json       VARCHAR DEFAULT '{}'
);
CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE UNIQUE INDEX idx_users_username ON users(username);
CREATE UNIQUE INDEX idx_users_corpus_id ON users(corpus_id);
CREATE INDEX idx_users_created ON users(created_at);
