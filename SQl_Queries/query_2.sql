WITH latest AS (
  SELECT
    SAFE_CAST(topics[SAFE_OFFSET(1)] AS INT64) AS agent_id,
    CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], 27)) AS owner,
    SAFE_CONVERT_BYTES_TO_STRING(FROM_HEX(SUBSTR(
      data, 131, 2 * SAFE_CAST(CONCAT('0x', SUBSTR(data, 67, 64)) AS INT64)))) AS agent_uri,
    block_timestamp,
    ROW_NUMBER() OVER (PARTITION BY SAFE_CAST(topics[SAFE_OFFSET(1)] AS INT64)
                       ORDER BY block_timestamp DESC) AS rn
  FROM `bigquery-public-data.goog_blockchain_ethereum_mainnet_us.logs`
  WHERE address = '0x8004a169fb4a3325136eb29fa0ceb6d2e539a432'
    AND topics[SAFE_OFFSET(0)] = '0xca52e62c367d81bb2e328eb795f7c7ba24afb478408a26c0e201d155c449bc4a'
    AND block_timestamp >= TIMESTAMP '2026-01-28'
)
SELECT
  agent_id, owner, agent_uri, block_timestamp AS registered_at,
  STARTS_WITH(agent_uri, 'data:application/json;base64,') AS fully_onchain,
  IF(STARTS_WITH(agent_uri, 'data:application/json;base64,'),
     SAFE_CONVERT_BYTES_TO_STRING(SAFE.FROM_BASE64(
       SUBSTR(agent_uri, LENGTH('data:application/json;base64,') + 1))), NULL) AS reg_json
FROM latest WHERE rn = 1;