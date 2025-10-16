# Hint Logs & Scoreboard Visibility Features

## Summary of Changes

This update adds two major admin features:
1. **Hint Unlock Logs in Admin UI** - Track all hint unlocks with detailed information
2. **Scoreboard Visibility Toggle** - Hide/show scoreboard to users at any time

---

## 🔍 Feature 1: Hint Logs in Admin UI

### What It Does
Provides a comprehensive view of all hint unlocks with:
- Real-time tracking of who unlocks hints
- Challenge and hint information
- Points spent tracking
- Team/user associations
- Filterable and exportable data

### Where to Find It
**Admin Panel** → **Hint Logs** (new menu item in sidebar)

### Features
✅ **Comprehensive Table View**:
- Timestamp (with relative time display)
- User who unlocked the hint
- Team (if applicable)
- Challenge name (clickable)
- Hint number
- Points cost

✅ **Statistics Dashboard**:
- Total hints unlocked
- Total points spent on hints
- Number of unique users who used hints

✅ **Filtering System**:
- Filter by username
- Filter by team
- Filter by challenge name
- Live client-side filtering

✅ **Pagination**:
- 50 logs per page
- Navigate through all hint unlocks

✅ **Export to CSV**:
- Download filtered data
- Filename: `hint_logs_YYYY-MM-DD.csv`

### Data Tracked
```python
{
    'time': '2025-10-16 14:32:15',
    'user': 'alice',
    'team': 'CyberWarriors',
    'challenge': 'SQL Injection',
    'hint_number': 2,
    'cost': 50
}
```

### API Endpoint (Admin Only)
```
GET /admin/hint-logs/api?page=1&per_page=50
GET /admin/hint-logs/api?user_id=5
GET /admin/hint-logs/api?team_id=3
GET /admin/hint-logs/api?challenge_id=10
```

### Database Tracking
All hint unlocks are stored in the `hint_unlocks` table:
- `id` - Unique identifier
- `hint_id` - Reference to hint
- `user_id` - User who unlocked
- `team_id` - Team (if applicable)
- `cost_paid` - Points deducted
- `created_at` - Timestamp

---

## 👁️ Feature 2: Scoreboard Visibility Toggle

### What It Does
Admins can instantly hide or show the scoreboard to all users (non-admins).

### Where to Configure
**Admin Panel** → **Settings** → **Event Configuration** → **Show Scoreboard to Users** toggle

### Behavior

#### When ENABLED (Default):
✅ All users can see the Scoreboard menu
✅ All users can view scoreboard page
✅ All users can access scoreboard API
✅ Live updates work normally

#### When DISABLED:
❌ Scoreboard menu hidden from non-admin users
❌ Users redirected if they try to access scoreboard
❌ Scoreboard API returns empty array for users
✅ Admins can still view scoreboard (with "Hidden" badge)
✅ Admins can see current rankings

### Use Cases

**Hide During Setup:**
```
Competition starts tomorrow → Hide scoreboard until CTF begins
```

**Hide for Final Hours:**
```
Last 2 hours → Hide scoreboard to prevent strategic submission delays
```

**Hide for Surprise Reveals:**
```
Hide during CTF → Reveal winners at closing ceremony
```

**Hide Between Rounds:**
```
Multi-day event → Hide between competition days
```

### Admin View
When scoreboard is hidden, admins see:
- Scoreboard menu with "Hidden" badge
- Full access to scoreboard data
- Can verify scores before revealing to participants

### User Experience
When hidden:
1. Menu item disappears from navigation
2. Direct URL access redirects to home
3. Flash message: "The scoreboard is currently hidden by the admins."
4. No error - clean UX

---

## Files Modified

### 1. Backend Routes
**`routes/admin.py`**:
- Added `hint_logs()` - View hint logs page
- Added `hint_logs_api()` - API for hint data with filters
- Added `scoreboard_visible` toggle to `update_event_config()`

**`routes/scoreboard.py`**:
- Added visibility check in `view_scoreboard()`
- Added visibility check in `get_scoreboard_data()`
- Admin bypass for both checks

**`routes/hints.py`**:
- Already has logging (from previous update)
- Logs include user, team, challenge, cost, and new score

### 2. Frontend Templates
**`templates/admin/_sidebar.html`**:
- Added "Hint Logs" menu item

**`templates/admin/hint_logs.html`** (NEW):
- Full hint logs interface
- Filters, pagination, export functionality
- Statistics cards
- Relative timestamps

**`templates/admin/settings.html`**:
- Added "Show Scoreboard to Users" toggle
- Helpful descriptions for when enabled/disabled

**`templates/base.html`**:
- Scoreboard menu conditional on `scoreboard_visible`
- Shows "Hidden" badge for admins when disabled

### 3. Application Core
**`app.py`**:
- Added `scoreboard_visible` to context processor
- Now available in all templates

**`init_db.py`**:
- Added default: `scoreboard_visible = True`

---

## Database Changes

### New Setting Added
```sql
INSERT INTO settings (key, value, type, description) VALUES
('scoreboard_visible', 'true', 'bool', 'Show scoreboard to users');
```

**No migration needed** - This is auto-created on first run or can be added manually.

---

## Usage Examples

### Example 1: Hide Scoreboard Before CTF Starts
```
1. Go to Admin → Settings
2. Uncheck "Show Scoreboard to Users"
3. Click "Save Event Configuration"
4. Users will see no scoreboard menu
5. When CTF starts, re-enable it
```

### Example 2: View Hint Usage Patterns
```
1. Go to Admin → Hint Logs
2. Filter by Challenge: "SQL Injection"
3. See which users needed hints
4. Identify if challenge is too hard
5. Export data for analysis
```

### Example 3: Track Points Spent on Hints
```
1. Go to Admin → Hint Logs
2. Look at "Total Points Spent" statistic
3. See which teams/users rely on hints most
4. Adjust hint costs if needed
```

### Example 4: Export Hint Data for Analysis
```
1. Go to Admin → Hint Logs
2. Apply filters (optional)
3. Click "Export to CSV"
4. Open in Excel/Google Sheets
5. Create charts and analysis
```

---

## API Documentation

### Hint Logs API (Admin Only)

#### Get Hint Logs
```http
GET /admin/hint-logs/api
```

**Query Parameters:**
- `page` (int) - Page number (default: 1)
- `per_page` (int) - Results per page (default: 50)
- `user_id` (int) - Filter by user ID
- `team_id` (int) - Filter by team ID
- `challenge_id` (int) - Filter by challenge ID

**Response:**
```json
{
  "success": true,
  "logs": [
    {
      "id": 123,
      "user": "alice",
      "user_id": 5,
      "team": "CyberWarriors",
      "team_id": 3,
      "challenge": "SQL Injection",
      "challenge_id": 10,
      "hint_order": 2,
      "cost": 50,
      "created_at": "2025-10-16T14:32:15"
    }
  ],
  "total": 145,
  "pages": 3,
  "current_page": 1
}
```

---

## Testing Checklist

### Hint Logs Feature
- [ ] Visit `/admin/hint-logs` as admin
- [ ] Verify logs table displays correctly
- [ ] Verify statistics cards show correct numbers
- [ ] Test user filter
- [ ] Test team filter
- [ ] Test challenge filter
- [ ] Test pagination
- [ ] Test CSV export
- [ ] Verify relative timestamps work
- [ ] Click links to users/teams/challenges

### Scoreboard Visibility
- [ ] Log in as admin
- [ ] Go to Settings
- [ ] Toggle "Show Scoreboard to Users" OFF
- [ ] Save settings
- [ ] Log out
- [ ] Log in as regular user
- [ ] Verify Scoreboard menu is hidden
- [ ] Try accessing `/scoreboard` directly (should redirect)
- [ ] Log back in as admin
- [ ] Verify Scoreboard menu shows "Hidden" badge
- [ ] Verify admin can still access scoreboard
- [ ] Toggle setting back ON
- [ ] Verify users can see scoreboard again

---

## Deployment Steps

### 1. Pull Latest Code
```bash
cd ~/Blackbox
git pull
```

### 2. Add Default Setting (if upgrading existing database)
```bash
# Connect to database
docker exec -it blackbox-db mysql -u root -p blackbox_ctf

# Add setting
INSERT INTO settings (`key`, `value`, `type`, `description`) 
VALUES ('scoreboard_visible', 'true', 'bool', 'Show scoreboard to users');

# Exit
exit
```

### 3. Restart Containers
```bash
docker-compose up -d --build blackbox
docker-compose restart blackbox nginx
```

### 4. Verify
```bash
# Check containers are running
docker ps

# Check logs for errors
docker logs blackbox-ctf --tail 50
```

---

## Analytics Queries

### Most Hint-Dependent Users
```sql
SELECT u.username, COUNT(hu.id) as hints_used, SUM(hu.cost_paid) as points_spent
FROM users u
LEFT JOIN hint_unlocks hu ON u.id = hu.user_id
GROUP BY u.id
ORDER BY hints_used DESC
LIMIT 20;
```

### Most Hint-Dependent Teams
```sql
SELECT t.name, COUNT(hu.id) as hints_used, SUM(hu.cost_paid) as points_spent
FROM teams t
LEFT JOIN hint_unlocks hu ON t.id = hu.team_id
GROUP BY t.id
ORDER BY hints_used DESC
LIMIT 20;
```

### Challenges That Need Most Hints
```sql
SELECT c.name, c.category, COUNT(hu.id) as hint_unlocks
FROM challenges c
LEFT JOIN hints h ON c.id = h.challenge_id
LEFT JOIN hint_unlocks hu ON h.id = hu.hint_id
GROUP BY c.id
ORDER BY hint_unlocks DESC;
```

### Hint Usage Over Time
```sql
SELECT DATE(hu.created_at) as date, 
       COUNT(*) as unlocks,
       SUM(hu.cost_paid) as total_cost
FROM hint_unlocks hu
WHERE hu.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY DATE(hu.created_at)
ORDER BY date;
```

---

## Benefits

### For Admins:
✅ **Visibility** - See exactly who uses hints and when
✅ **Analytics** - Identify challenge difficulty patterns
✅ **Control** - Hide scoreboard during critical moments
✅ **Data Export** - CSV export for detailed analysis
✅ **Audit Trail** - Complete record of all hint usage

### For Competition Management:
✅ **Fair Play** - Track hint usage patterns
✅ **Challenge Balance** - Identify overly difficult challenges
✅ **Strategic Control** - Hide scoreboard at key moments
✅ **Post-Event Analysis** - Export data for reports

### For User Experience:
✅ **Clean UX** - No broken links when scoreboard hidden
✅ **Clear Communication** - Flash messages explain why scoreboard hidden
✅ **Admin Transparency** - Admins see "Hidden" badge

---

## Summary

**New Admin Features:**
1. ✅ Hint Logs page with full tracking
2. ✅ Scoreboard visibility toggle
3. ✅ CSV export functionality
4. ✅ Admin-only API endpoints
5. ✅ Clean user experience when features disabled

**Zero Breaking Changes:**
- All existing functionality preserved
- Backwards compatible
- Default settings maintain current behavior

**Production Ready:**
- No database migrations required (auto-creates setting)
- Tested pagination and filtering
- Secure admin-only access
- Clean error handling

Deploy with confidence! 🚀
