CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'user')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE faces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(event_id),
    image_id UUID,
    face_embedding vector(512) NOT NULL
);

CREATE INDEX faces_event_id_idx ON faces(event_id);
CREATE INDEX faces_embedding_idx ON faces USING ivfflat (face_embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(event_id),
    filename VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    thumbnail_url VARCHAR(255),
    uploaded_by UUID REFERENCES users(user_id),
    consent_given BOOLEAN NOT NULL
);

CREATE INDEX images_event_id_idx ON images(event_id);
CREATE INDEX images_timestamp_idx ON images(timestamp);

CREATE TABLE consents (
    consent_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id),
    image_id UUID REFERENCES images(id),
    consent_given BOOLEAN NOT NULL,
    consent_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id),
    action VARCHAR(50) NOT NULL,
    details JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notification_sent BOOLEAN DEFAULT FALSE
);

CREATE INDEX logs_timestamp_idx ON logs(timestamp);
CREATE INDEX logs_action_idx ON logs(action);
CREATE INDEX logs_user_id_idx ON logs(user_id);
