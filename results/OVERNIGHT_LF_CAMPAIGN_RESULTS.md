# Overnight LF-fixed campaign results

Elapsed_s: 59685.8

## Oracle gold n=100
- Resolve@1: **0.89**
- Counts: `{'resolved': 89, 'unresolved': 2, 'error': 9, 'missing': 0, 'scored': 100}`

## VI.B LF rescore (supersedes CRLF-era Resolve@1)
- **cr_guided**: Resolve@1=0.02 counts={'resolved': 2, 'unresolved': 6, 'error': 92, 'missing': 0, 'scored': 100}
- **reward_only**: Resolve@1=0.04 counts={'resolved': 4, 'unresolved': 15, 'error': 81, 'missing': 0, 'scored': 100}
- **random**: Resolve@1=0.03 counts={'resolved': 3, 'unresolved': 16, 'error': 81, 'missing': 0, 'scored': 100}
- **static_heuristic**: Resolve@1=0.03 counts={'resolved': 3, 'unresolved': 16, 'error': 81, 'missing': 0, 'scored': 100}

## CR-guided failure taxonomy
`{'wrong_path': 34, 'malformed_diff': 17, 'hunk_mismatch': 41, 'other_apply': 0, 'resolved': 2, 'applied_tests_fail': 6, 'missing': 0}`

CommSCM core unchanged. Batched eval with cache_level=instance.
