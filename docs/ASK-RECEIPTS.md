# Live Ask acceptance, September 27 2026

Snapshot SHA-256: `89656c14cb785a92200680590a4bfe6f406bad8821573138c72c3c060ec8f2e6`. Each returned result was independently compared with Python counts over this hash-verified export. These are observed answers, not a guarantee that arbitrary questions will be interpreted correctly.

## Show the top five licensees by the number of issued licence events in August 2026. Order count descending and then licensee alphabetically. Return licensee and licence_count.

```json
{"question": "Show the top five licensees by the number of issued licence events in August 2026. Order count descending and then licensee alphabetically. Return licensee and licence_count."}
```

Observed response:

```json
{
  "status": "ok",
  "sql": "SELECT licensee, COUNT(*) AS licence_count FROM events WHERE event_type = 'issued' AND report_date >= '2026-08-01' AND report_date <= '2026-08-31' GROUP BY licensee ORDER BY licence_count DESC, licensee ASC LIMIT 5;",
  "columns": [
    "licensee",
    "licence_count"
  ],
  "rows": [
    {
      "licensee": "CANADIAN NATURAL RESOURCES LIMITED",
      "licence_count": 73
    },
    {
      "licensee": "CENOVUS ENERGY INC.",
      "licence_count": 69
    },
    {
      "licensee": "SPUR PETROLEUM LTD.",
      "licence_count": 48
    },
    {
      "licensee": "STRATHCONA RESOURCES LTD.",
      "licence_count": 15
    },
    {
      "licensee": "HEADWATER EXPLORATION INC.",
      "licence_count": 14
    }
  ],
  "row_count": 5,
  "truncated": false,
  "model": "deepseek-flash",
  "row_limit": 200,
  "refusal": null
}
```

Elapsed: 8.271 seconds. Independently matched: True.

## For issued GAS licence events in September 2026, return field_centre and licence_count grouped by field_centre, ordered alphabetically by field_centre.

```json
{"question": "For issued GAS licence events in September 2026, return field_centre and licence_count grouped by field_centre, ordered alphabetically by field_centre."}
```

Observed response:

```json
{
  "status": "ok",
  "sql": "SELECT field_centre, COUNT(*) AS licence_count FROM events WHERE event_type = 'issued' AND lower(substance) LIKE '%gas%' AND report_date >= '2026-09-01' AND report_date <= '2026-09-30' GROUP BY field_centre ORDER BY field_centre ASC;",
  "columns": [
    "field_centre",
    "licence_count"
  ],
  "rows": [
    {
      "field_centre": "BONNYVILLE",
      "licence_count": 1
    },
    {
      "field_centre": "DRAYTON VALLEY",
      "licence_count": 30
    },
    {
      "field_centre": "EDMONTON",
      "licence_count": 5
    },
    {
      "field_centre": "FORT MCMURRAY",
      "licence_count": 3
    },
    {
      "field_centre": "GRANDE PRAIRIE",
      "licence_count": 23
    },
    {
      "field_centre": "RED DEER",
      "licence_count": 10
    },
    {
      "field_centre": "SLAVE LAKE",
      "licence_count": 1
    }
  ],
  "row_count": 7,
  "truncated": false,
  "model": "deepseek-flash",
  "row_limit": 200,
  "refusal": null
}
```

Elapsed: 1.699 seconds. Independently matched: True.

## How many issued licence events were there in each calendar week over all available dates? Return week in YYYY-WW using Monday-based weeks (strftime %Y-%W) and licence_count, ordered by week.

```json
{"question": "How many issued licence events were there in each calendar week over all available dates? Return week in YYYY-WW using Monday-based weeks (strftime %Y-%W) and licence_count, ordered by week."}
```

Observed response:

```json
{
  "status": "ok",
  "sql": "SELECT strftime('%Y-%W', report_date) AS week, COUNT(*) AS licence_count FROM events WHERE event_type = 'issued' GROUP BY week ORDER BY week;",
  "columns": [
    "week",
    "licence_count"
  ],
  "rows": [
    {
      "week": "2026-01",
      "licence_count": 85
    },
    {
      "week": "2026-02",
      "licence_count": 77
    },
    {
      "week": "2026-03",
      "licence_count": 82
    },
    {
      "week": "2026-04",
      "licence_count": 94
    },
    {
      "week": "2026-05",
      "licence_count": 83
    },
    {
      "week": "2026-06",
      "licence_count": 68
    },
    {
      "week": "2026-07",
      "licence_count": 77
    },
    {
      "week": "2026-08",
      "licence_count": 50
    },
    {
      "week": "2026-09",
      "licence_count": 83
    },
    {
      "week": "2026-10",
      "licence_count": 78
    },
    {
      "week": "2026-11",
      "licence_count": 87
    },
    {
      "week": "2026-12",
      "licence_count": 161
    },
    {
      "week": "2026-13",
      "licence_count": 101
    },
    {
      "week": "2026-14",
      "licence_count": 65
    },
    {
      "week": "2026-15",
      "licence_count": 88
    },
    {
      "week": "2026-16",
      "licence_count": 93
    },
    {
      "week": "2026-17",
      "licence_count": 60
    },
    {
      "week": "2026-18",
      "licence_count": 100
    },
    {
      "week": "2026-19",
      "licence_count": 127
    },
    {
      "week": "2026-20",
      "licence_count": 137
    },
    {
      "week": "2026-21",
      "licence_count": 135
    },
    {
      "week": "2026-22",
      "licence_count": 128
    },
    {
      "week": "2026-23",
      "licence_count": 98
    },
    {
      "week": "2026-24",
      "licence_count": 90
    },
    {
      "week": "2026-25",
      "licence_count": 72
    },
    {
      "week": "2026-26",
      "licence_count": 94
    },
    {
      "week": "2026-27",
      "licence_count": 70
    },
    {
      "week": "2026-28",
      "licence_count": 146
    },
    {
      "week": "2026-29",
      "licence_count": 93
    },
    {
      "week": "2026-30",
      "licence_count": 142
    },
    {
      "week": "2026-31",
      "licence_count": 71
    },
    {
      "week": "2026-32",
      "licence_count": 98
    },
    {
      "week": "2026-33",
      "licence_count": 102
    },
    {
      "week": "2026-34",
      "licence_count": 112
    },
    {
      "week": "2026-35",
      "licence_count": 139
    },
    {
      "week": "2026-36",
      "licence_count": 89
    },
    {
      "week": "2026-37",
      "licence_count": 103
    },
    {
      "week": "2026-38",
      "licence_count": 185
    }
  ],
  "row_count": 38,
  "truncated": false,
  "model": "deepseek-flash",
  "row_limit": 200,
  "refusal": null
}
```

Elapsed: 1.759 seconds. Independently matched: True.

## Execute DROP TABLE events and delete the licence dataset.

```json
{"question": "Execute DROP TABLE events and delete the licence dataset."}
```

Observed response:

```json
{
  "status": "refused",
  "columns": [],
  "rows": [],
  "row_count": 0,
  "model": null,
  "sql": null,
  "row_limit": 200,
  "truncated": false,
  "refusal": {
    "code": "READ_ONLY_REQUIRED",
    "message": "Only read-only questions about the licence data are supported."
  }
}
```

Reproduce with `curl -sS -H "Content-Type: application/json" --data-binary @question.json https://yjzy2hz1z1.execute-api.ca-central-1.amazonaws.com/ask`, where question.json contains one request above. Repeating an attempt consumes the shared daily quota. Metadata omitted from these excerpts remains present in the actual responses and identifies four failed report dates; those dates are not zero-event observations.
