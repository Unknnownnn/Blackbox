CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sent_by INT NULL,
    CONSTRAINT fk_notifications_user FOREIGN KEY (sent_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_notifications_created_at (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;