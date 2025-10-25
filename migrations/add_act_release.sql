-- Migration: add act_releases table for admin-controlled ACT releases
CREATE TABLE IF NOT EXISTS `act_releases` (
  `act` varchar(20) NOT NULL,
  `is_released` tinyint(1) NOT NULL DEFAULT 0,
  `unlocked_at` datetime DEFAULT NULL,
  `unlocked_by_admin_id` int DEFAULT NULL,
  PRIMARY KEY (`act`),
  KEY `idx_act_releases_is_released` (`is_released`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed default acts: ACT I released, others locked
INSERT IGNORE INTO `act_releases` (`act`, `is_released`) VALUES
('ACT I', 1),
('ACT II', 0),
('ACT III', 0),
('ACT IV', 0),
('ACT V', 0);
