CREATE TABLE IF NOT EXISTS notification_reads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    notification_id INT NOT NULL,
    user_id INT NOT NULL,
    read_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uix_notification_user (notification_id, user_id),
    CONSTRAINT fk_notification_reads_notification FOREIGN KEY (notification_id)
        REFERENCES notifications(id) ON DELETE CASCADE,
    CONSTRAINT fk_notification_reads_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
