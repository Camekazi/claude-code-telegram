# User Context for Claude

This context is automatically loaded with every Claude session via Telegram.

## Quick Access Paths

| Resource | Path |
|----------|------|
| Groceries DB | `/Users/joppa/eobsidian/02_Areas/Family/groceries.db` |
| Obsidian Vault | `/Users/joppa/eobsidian` |
| Projects | `/Users/joppa/Projects` |
| Claude Config | `/Users/joppa/.claude` |

## Grocery Database Schema

```sql
-- Query with: sqlite3 /Users/joppa/eobsidian/02_Areas/Family/groceries.db
purchases (date, store, product, category, quantity, unit, price, email_id)
nutrition (food_name, category, calories_per_100g, protein, carbs, sugars, fat, nutri_score, zoe_notes)
zoe_profiles (person, metric, value, value_text, status, notes)
```

## Family Context

- **Ewan**: Has Zoe nutrition profile focused on blood sugar control
- **Emily**: Has Zoe nutrition profile
- **Stores used**: Waitrose, ASDA, Mindful Chef, Stocked

## User Preferences

- Prefers concise responses
- Likes tables for data comparisons
- Uses £ for currency
- Located in Edinburgh, UK
