SELECT
  '📊 Trade Statistics' as section;

SELECT
  'Total trades' as metric,
  COUNT(*) as value
FROM on_chain_trades
UNION ALL
SELECT
  'Mapped trades',
  COUNT(CASE WHEN condition_id IS NOT NULL THEN 1 END)
FROM on_chain_trades
UNION ALL
SELECT
  'Unmapped trades',
  COUNT(CASE WHEN condition_id IS NULL THEN 1 END)
FROM on_chain_trades
UNION ALL
SELECT
  'Unique markets',
  COUNT(DISTINCT condition_id)
FROM on_chain_trades WHERE condition_id IS NOT NULL
UNION ALL
SELECT
  'Coverage %',
  ROUND(100.0 * COUNT(CASE WHEN condition_id IS NOT NULL THEN 1 END) / COUNT(*), 1)
FROM on_chain_trades;
