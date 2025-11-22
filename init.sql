-- PriceFlow - Script d'initialisation de la base de données
-- Ce script est exécuté automatiquement au premier lancement du conteneur PostgreSQL

-- Extension pour les UUID (optionnel, pour future utilisation)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table des profils de notification
CREATE TABLE IF NOT EXISTS notification_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    apprise_url VARCHAR(1024),
    notify_on_price_drop BOOLEAN DEFAULT TRUE,
    notify_on_target_price BOOLEAN DEFAULT TRUE,
    price_drop_threshold_percent FLOAT DEFAULT 10.0,
    notify_on_stock_change BOOLEAN DEFAULT TRUE,
    check_interval_minutes INTEGER DEFAULT 60
);

-- Index sur le nom du profil
CREATE INDEX IF NOT EXISTS idx_notification_profiles_name ON notification_profiles(name);

-- Table des articles suivis
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    url VARCHAR(2048) NOT NULL,
    name VARCHAR(512) NOT NULL,
    selector VARCHAR(512),
    target_price FLOAT,
    check_interval_minutes INTEGER DEFAULT 60,
    current_price FLOAT,
    in_stock BOOLEAN,
    tags VARCHAR(512),
    description TEXT,
    current_price_confidence FLOAT,
    in_stock_confidence FLOAT,
    is_active BOOLEAN DEFAULT TRUE,
    last_checked TIMESTAMP,
    is_refreshing BOOLEAN DEFAULT FALSE,
    last_error VARCHAR(1024),
    notification_profile_id INTEGER REFERENCES notification_profiles(id) ON DELETE SET NULL
);

-- Index sur les articles
CREATE INDEX IF NOT EXISTS idx_items_url ON items(url);
CREATE INDEX IF NOT EXISTS idx_items_is_active ON items(is_active);
CREATE INDEX IF NOT EXISTS idx_items_notification_profile_id ON items(notification_profile_id);

-- Table de l'historique des prix
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    price FLOAT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    screenshot_path VARCHAR(512),
    price_confidence FLOAT,
    in_stock_confidence FLOAT,
    ai_model VARCHAR(255),
    ai_provider VARCHAR(100),
    prompt_version VARCHAR(50),
    repair_used BOOLEAN DEFAULT FALSE
);

-- Index sur l'historique des prix
CREATE INDEX IF NOT EXISTS idx_price_history_item_id ON price_history(item_id);
CREATE INDEX IF NOT EXISTS idx_price_history_timestamp ON price_history(timestamp);

-- Table des paramètres
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT
);

-- Index sur les paramètres
CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);

-- Paramètres par défaut pour l'application
INSERT INTO settings (key, value) VALUES
    ('ai_provider', 'ollama'),
    ('ai_model', 'gemma3:4b'),
    ('ai_api_base', 'http://ollama:11434'),
    ('ai_temperature', '0.1'),
    ('ai_max_tokens', '300'),
    ('ai_timeout', '30'),
    ('enable_json_repair', 'true'),
    ('enable_multi_sample', 'false'),
    ('multi_sample_confidence_threshold', '0.6'),
    ('confidence_threshold_price', '0.5'),
    ('confidence_threshold_stock', '0.5'),
    ('smart_scroll_enabled', 'false'),
    ('smart_scroll_pixels', '350'),
    ('text_context_enabled', 'false'),
    ('text_context_length', '5000'),
    ('scraper_timeout', '90000'),
    ('refresh_interval_minutes', '60')
ON CONFLICT (key) DO NOTHING;

-- Message de fin d'initialisation
DO $$
BEGIN
    RAISE NOTICE 'PriceFlow database initialized successfully!';
END $$;
