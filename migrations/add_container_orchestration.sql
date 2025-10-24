CREATE TABLE IF NOT EXISTS container_instances (
    id INT AUTO_INCREMENT PRIMARY KEY,
    challenge_id INT NOT NULL,
    user_id INT NOT NULL,
    team_id INT,
    
    -- Docker container details
    container_id VARCHAR(128) NOT NULL UNIQUE,
    container_name VARCHAR(256) NOT NULL,
    docker_image VARCHAR(256) NOT NULL,
    
    -- Network details
    port INT NOT NULL,
    host_ip VARCHAR(256),
    host_port INT,
    ip_address VARCHAR(45),
    docker_info JSON,
    
    -- State tracking
    status VARCHAR(20) DEFAULT 'starting',
    session_id VARCHAR(64) NOT NULL UNIQUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    expires_at TIMESTAMP NOT NULL,
    last_revert_time TIMESTAMP NULL,
    
    -- Error tracking
    error_message TEXT,
    
    -- Foreign keys
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_challenge_user (challenge_id, user_id),
    INDEX idx_user (user_id),
    INDEX idx_status (status),
    INDEX idx_session (session_id),
    INDEX idx_expires (expires_at),
    INDEX idx_container (container_id)
);

-- Create container_events table for audit logging
CREATE TABLE IF NOT EXISTS container_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    container_instance_id INT,
    challenge_id INT NOT NULL,
    user_id INT NOT NULL,
    
    -- Event details
    event_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    
    -- Metadata
    ip_address VARCHAR(45),
    container_id VARCHAR(128),
    
    -- Timestamp
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (container_instance_id) REFERENCES container_instances(id) ON DELETE SET NULL,
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_event_type (event_type),
    INDEX idx_timestamp (timestamp),
    INDEX idx_user (user_id),
    INDEX idx_challenge (challenge_id)
);
