DELETE FROM users WHERE username = 'admin';
INSERT INTO users (username, password_hash, is_admin)
VALUES ('admin', '$2b$12$1bs.lMmsO5iuv3.fP7oU3eNCspUfHUPeyOKUXx3mZKTdLu/vsYurq', true);
SELECT username, password_hash FROM users WHERE username = 'admin';
