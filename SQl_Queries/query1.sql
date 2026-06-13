SELECT
  SAFE_CAST(topics[SAFE_OFFSET(1)] AS INT64) AS agent_id,
  CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], 27)) AS client,
  topics[SAFE_OFFSET(3)] AS tag_hash,
  SAFE_CAST(CONCAT('0x', SUBSTR(data, 67, 64)) AS INT64)
    / POW(10, SAFE_CAST(CONCAT('0x', SUBSTR(data, 131, 64)) AS INT64)) AS score,
  block_timestamp
FROM `bigquery-public-data.goog_blockchain_ethereum_mainnet_us.logs`
WHERE address = '0x8004baa17c55a88189ae136b182e5fda19de9b63'
  AND topics[SAFE_OFFSET(0)] = '0x6a4a61743519c9d648a14e6493f47dbe3ff1aa29e7785c96c8326a205e58febc'
  AND block_timestamp >= TIMESTAMP '2026-01-28'
  AND SUBSTR(data, 67, 1) != 'f';

