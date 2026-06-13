SELECT
  topics[SAFE_OFFSET(3)] AS tag_hash,
  SAFE_CONVERT_BYTES_TO_STRING(FROM_HEX(SUBSTR(
    data,
    3 + 2*SAFE_CAST(CONCAT('0x', SUBSTR(data,195,64)) AS INT64) + 64,
    2*SAFE_CAST(CONCAT('0x', SUBSTR(data,
        3 + 2*SAFE_CAST(CONCAT('0x', SUBSTR(data,195,64)) AS INT64), 64)) AS INT64)
  ))) AS tag_name,
  COUNT(*) AS n
FROM `bigquery-public-data.goog_blockchain_ethereum_mainnet_us.logs`
WHERE address = '0x8004baa17c55a88189ae136b182e5fda19de9b63'
  AND topics[SAFE_OFFSET(0)] = '0x6a4a61743519c9d648a14e6493f47dbe3ff1aa29e7785c96c8326a205e58febc'
  AND block_timestamp >= TIMESTAMP '2026-01-28'
GROUP BY tag_hash, tag_name
ORDER BY n DESC;