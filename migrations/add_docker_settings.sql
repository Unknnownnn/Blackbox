CREATE TABLE IF NOT EXISTS docker_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hostname VARCHAR(256),
    tls_enabled BOOLEAN DEFAULT FALSE,
    ca_cert TEXT,
    client_cert TEXT,
    client_key TEXT,
    allowed_repositories TEXT,
    max_containers_per_user INT DEFAULT 1,
    container_lifetime_minutes INT DEFAULT 120,
    revert_cooldown_minutes INT DEFAULT 5,
    port_range_start INT DEFAULT 30000,
    port_range_end INT DEFAULT 60000,
    auto_cleanup_on_solve BOOLEAN DEFAULT TRUE,
    cleanup_stale_containers BOOLEAN DEFAULT TRUE,
    stale_container_hours INT DEFAULT 2,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_hostname (hostname)
);

-- Add Docker-related fields to challenges table
ALTER TABLE challenges 
ADD COLUMN docker_enabled BOOLEAN DEFAULT FALSE AFTER connection_info,
ADD COLUMN docker_image VARCHAR(256) AFTER docker_enabled,
ADD COLUMN docker_connection_info VARCHAR(512) AFTER docker_image,
ADD INDEX idx_docker_enabled (docker_enabled);

-- Insert default Docker settings
INSERT INTO docker_settings (
    hostname,
    tls_enabled,
    max_containers_per_user,
    container_lifetime_minutes,
    revert_cooldown_minutes,
    port_range_start,
    port_range_end,
    auto_cleanup_on_solve,
    cleanup_stale_containers,
    stale_container_hours
) VALUES (
    NULL,  -- Empty = use local Docker socket
    FALSE,
    1,
    120,
    5,
    30000,
    60000,
    TRUE,
    TRUE,
    2
) ON DUPLICATE KEY UPDATE id=id;
