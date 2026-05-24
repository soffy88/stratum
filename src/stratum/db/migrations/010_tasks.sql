CREATE TABLE tasks (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    text VARCHAR NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    due_date DATE,
    scheduled_date DATE,
    tags VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
