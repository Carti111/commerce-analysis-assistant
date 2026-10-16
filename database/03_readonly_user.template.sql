-- Optional manual alternative to scripts/import_database.py.
-- Replace the password placeholder BEFORE running. Run as a database administrator.
-- Do not run this if import_database.py already created the account.
CREATE USER 'commerce_reader'@'%' IDENTIFIED BY 'REPLACE_WITH_YOUR_RANDOM_PASSWORD';
GRANT SELECT ON commerce_ai_demo.customers TO 'commerce_reader'@'%';
GRANT SELECT ON commerce_ai_demo.products TO 'commerce_reader'@'%';
GRANT SELECT ON commerce_ai_demo.orders TO 'commerce_reader'@'%';
GRANT SELECT ON commerce_ai_demo.order_items TO 'commerce_reader'@'%';
SHOW GRANTS FOR 'commerce_reader'@'%';
