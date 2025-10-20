# BlackBox CTF Platform

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-brightgreen.svg)

A modern, feature-rich Capture The Flag (CTF) platform built with Flask, designed for hosting cybersecurity competitions with advanced challenge management, real-time scoring, and comprehensive admin controls.

[Features](#features) • [Quick Start](#quick-start) • [Installation](#installation) • [Documentation](#documentation) • [Contributing](#contributing)

</div>

---
![Image](images/image1.png)

## Features

### Core Functionality

#### Challenge Management
- **Multiple Challenge Types**: Web, Crypto, Forensics, Reverse Engineering, Binary Exploitation, OSINT, etc.
- **Dynamic Scoring**: Point values adjust based on solve count (logarithmic, linear, or exponential decay)
- **Static Scoring**: Fixed point values for traditional CTF format
- **First Blood Bonus**: Configurable bonus points for first solver
- **File Attachments**: Upload challenge files with automatic hashing and integrity verification
- **Challenge Images**: Add inline images to challenge descriptions (similar to CTFd)
- **Connection Info**: Display SSH/netcat/web URLs for remote challenges
- **Challenge Flags**: Support for multiple flags per challenge (primary + alternative)
- **Case-Insensitive Flags**: Optional flag matching configuration

#### Advanced Challenge Features

![alt text](images/image2.png)

- **Challenge Branching & Prerequisites**:
  - Set prerequisite challenges that must be solved first
  - Flag-based unlocking (solving challenge A with specific flag unlocks challenge B)
  - Simple branching (linear progression)
  - Complex branching (multiple paths and dependencies)
  - Visual dependency graph in admin panel

#### Hint System
- **Progressive Hints**: Multiple hints per challenge with point costs
- **Hint Prerequisites**: Hints can require previous hints to be unlocked first
- **Team Requirements**: Limit hints to team mode only
- **Cost Deduction**: Automatic point deduction from team/user score
- **Unlock History**: Track who unlocked which hints and when
- **Admin Hint Logs**: Comprehensive logging of all hint unlocks with filtering

#### Team System
- **Flexible Team Modes**
  - Solo mode (individual competition)
  - Team mode (collaborative solving)
  - Optional teams (mix of solo and team players)
- **Team Management**:
  - Create teams with invite codes
  - Join teams via invite code or captain approval
  - Team size limits (configurable)
  - Team captain controls
  - Kick members
  - Leave team functionality
- **Team Scoring**: Aggregate team scores with solve tracking
- **Team Profiles**: View team members, solves, and statistics

#### User Management
- **Registration System**: Optional user registration (can be disabled for admin-only user creation)
- **Authentication**: Secure login/logout with Flask-Login
- **User Profiles**: View solve history, hints unlocked, team membership
- **Admin Roles**: Dedicated admin panel with full platform control
- **Password Security**: Bcrypt password hashing

### Scoring & Competition

#### Real-Time Scoreboard
- **Live Updates**: WebSocket-based real-time score updates
- **Team/Solo Rankings**: Separate scoreboards for team and solo modes
- **Solve Timeline**: Visual timeline of challenge solves
- **Score History**: Track score progression over time
- **First Blood Indicators**: Highlight first solvers
- **Scoreboard Visibility**: Admin can hide/show scoreboard to users

#### Submission Tracking
- **Attempt Limits**: Optional rate limiting for flag submissions
- **Solve Tracking**: Record solve times, user/team, and points awarded
- **Manual Point Adjustments**: Admins can manually adjust scores with reason logging
- **Solve History**: View all solves with timestamps and point values
- **User Activity**: Comprehensive solve and hint unlock logs per user

#### CTF Control
- **Scheduled Events**: Set start and end times for competition
- **Timezone Support**: Full timezone configuration (16 common timezones)
- **Pause/Resume**: Pause submissions without ending the CTF
- **Always-On Mode**: Run continuous CTF without time limits
- **Countdown Timer**: Automatic countdown page before event starts
- **Event Status**: Track if CTF is running, paused, scheduled, or ended

### User Interface

#### Modern Design
- **Bootstrap 5**: Responsive, mobile-friendly interface
- **Bootstrap Icons**: Comprehensive icon set
- **Dark/Light Themes**: Clean, professional design
- **Custom Backgrounds**: Animated gradient backgrounds with live preview
- **Matrix Effects**: Cyber-themed background options
- **Smooth Animations**: CSS transitions and hover effects

#### Admin Panel
- **Dashboard**: Overview of platform stats, recent activity
- **Challenge Manager**: 
  - Create/edit/delete challenges
  - Bulk operations
  - Visual branching editor
  - Card-based UI with colored sections
- **User Management**: View users, adjust points, track activity
- **Team Management**: Manage teams, adjust scores, view members
- **Hint Management**: Create/edit/delete hints, view unlock logs
- **Settings**: Configure platform, event details, branding
- **CTF Control**: Manage competition timing and status
- **Backup System**: Automated and manual backups

### Security Features

#### Application Security
- **CSRF Protection**: Flask-WTF CSRF tokens on all forms
- **Security Headers**: 
  - Content Security Policy (CSP)
  - X-Content-Type-Options
  - X-Frame-Options
  - Strict-Transport-Security
  - X-XSS-Protection
- **SQL Injection Prevention**: SQLAlchemy ORM with parameterized queries
- **XSS Protection**: Template auto-escaping with Jinja2
- **Password Security**: Bcrypt hashing with salts
- **Session Security**: 
  - HTTPOnly cookies
  - Secure cookies (HTTPS)
  - SameSite protection
  - Configurable session lifetime

#### File Upload Security
- **File Type Validation**: Whitelist of allowed extensions
- **Size Limits**: Configurable max upload size (default 50MB)
- **Secure Filenames**: Werkzeug secure_filename sanitization
- **Hash Verification**: SHA256 checksums for file integrity
- **Isolated Storage**: Files stored outside web root

### Performance & Scalability

#### Caching
- **Redis Caching**: Distributed caching for high availability
- **Settings Cache**: 5-minute TTL for database settings
- **Challenge Cache**: Invalidation on updates
- **Session Storage**: Redis-based sessions for horizontal scaling

#### Database Optimization
- **Connection Pooling**: Configurable pool size and overflow
- **Query Optimization**: Indexed columns for fast lookups
- **Lazy Loading**: Efficient relationship loading
- **Transaction Management**: Proper commit/rollback handling
- **Pool Pre-Ping**: Automatic stale connection detection

#### Real-Time Features
- **Socket.IO**: WebSocket support for live updates
- **Eventlet**: Async worker for concurrent connections
- **Live Scoreboard**: Instant score updates without page refresh
- **Event Broadcasting**: Challenge solves broadcast to all users

### Administration Tools

#### Backup System
- **Automated Backups**: Scheduled backups (hourly/daily/weekly/monthly)
- **Manual Backups**: One-click backup creation
- **Backup Frequency Configuration**: Choose backup schedule
- **Timezone-Aware**: Backup times respect platform timezone
- **Compressed Storage**: Gzip-compressed SQL dumps
- **Metadata Tracking**: JSON metadata for each backup
- **Restore Functionality**: One-click database restore
- **Backup Cleanup**: Auto-delete old automatic backups (keeps last 10)
- **Upload/Download**: Import and export backup files

#### Platform Configuration
- **Event Settings**:
  - CTF name and description
  - Logo upload
  - Registration toggle
  - Team mode toggle
  - Scoreboard visibility
  - First blood bonus
- **System Settings**:
  - Timezone configuration (16 timezones supported)
  - Backup frequency
  - Automatic backup scheduling
- **Custom Theming**:
  - Custom CSS backgrounds
  - Live preview
  - Example templates (gradients, matrix, cyber grid, starfield)
  - Safe CSS validation

#### Monitoring & Logs
- **Health Check Endpoint**: Database and Redis status monitoring
- **User Activity Logs**: Track all user actions and submissions
- **Hint Unlock Logs**: Comprehensive hint unlock history
- **Solve History**: Detailed solve timeline with points
- **Admin Actions**: Logged point adjustments with reasons

### Internationalization

#### Timezone Support
- **Platform Timezone**: Configure global timezone (default UTC)
- **Supported Timezones**:
  - UTC
  - US: Eastern, Central, Mountain, Pacific
  - Europe: London, Paris, Berlin, Moscow
  - Asia: Dubai, Kolkata, Shanghai, Tokyo, Singapore
  - Pacific: Sydney, Auckland
- **Timezone Conversion**: All timestamps display in configured timezone
- **CTF Scheduling**: Set start/end times in platform timezone
- **Backup Times**: Scheduled backups respect timezone
- **User Activity**: All logs show times in platform timezone

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### Installation (Docker - Recommended)

```bash
# Clone the repository
git clone https://github.com/Unknnownnn/Blackbox.git
cd Blackbox

# Start the platform
docker-compose up -d --build

# Access the platform
# Web: http://localhost:8000
# Admin setup: http://localhost:8000/setup
```

That's it! The platform will be running with:
- Flask application on port 8000
- MariaDB database
- Redis cache

### First-Time Setup

1. **Navigate to Setup Page**: http://localhost:5000/setup
2. **Create Admin Account**:
   - Username: `admin`
   - Email: `admin@example.com`
   - Password: (your secure password)
3. **Configure Event**:
   - CTF Name
   - Description
   - Upload logo (optional)
4. **Set Timezone**: Admin → Settings → System Settings
5. **Configure CTF Schedule**: Admin → CTF Control

---

## Installation Options

### Option 1: Docker (Production)

```bash
# Clone repository
git clone https://github.com/Unknnownnn/Blackbox.git
cd Blackbox

# Configure environment (optional)
cp .env.example .env
nano .env

# Start services
docker-compose up -d --build

# View logs
docker-compose logs -f blackbox

# Stop services
docker-compose down
```

### Option 2: Manual Installation (Development)

```bash
# Clone repository
git clone https://github.com/Unknnownnn/Blackbox.git
cd Blackbox

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up database
# Install MariaDB/MySQL and Redis

# Configure environment
cp .env.example .env
# Edit .env with your database and Redis credentials

# Initialize database
python init_db.py

# Start the application
python app.py

# Or with Gunicorn (production)
gunicorn -c gunicorn.conf.py app:app
```

### Environment Variables

Create a `.env` file with the following:

```env
# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=production
DEBUG=false

# Database
DATABASE_URL=mysql+pymysql://blackbox_user:secure_password@blackbox-db:3306/ctf_platform

# Redis
REDIS_URL=redis://blackbox-redis:6379/0

# Application
CTF_NAME=My_CTF
CTF_DESCRIPTION=Sample_Text
REGISTRATION_ENABLED=true

# File Uploads
MAX_UPLOAD_SIZE=52428800  

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4
```

---


## Usage Guide

### For Participants

#### Getting Started
1. **Register**: Create an account (if registration is enabled)
2. **Join/Create Team**: If team mode is enabled
3. **Browse Challenges**: Navigate to Challenges page
4. **View Challenge**: Click on a challenge to see details
5. **Submit Flag**: Enter the flag and submit
6. **Use Hints**: Unlock hints if you're stuck (costs points)
7. **Track Progress**: View scoreboard and your profile

#### Solving Challenges
- Each challenge has a category, difficulty, and point value
- Some challenges may have file attachments to download
- Connection info provided for remote challenges
- Multiple flags may be accepted (case-insensitive option)
- First blood bonus awarded to first solver

### For Administrators

#### Creating Challenges
1. **Admin Panel → Challenges → Create Challenge**
2. **Fill Basic Information**:
   - Challenge name
   - Category (Web, Crypto, Forensics, etc.)
   - Difficulty (Easy, Medium, Hard, Expert)
   - Description (supports Markdown)
3. **Add Challenge Images** (optional):
   - Upload images to display in description
   - Images appear below description text
4. **Set Scoring**:
   - Static: Fixed points
   - Dynamic: Points decrease with solves
5. **Add Flags**:
   - Primary flag (required)
   - Alternative flags (optional)
   - Case-sensitive toggle
6. **Upload Files** (optional):
   - Challenge files for participants
   - Automatic hash generation
7. **Connection Info** (optional):
   - SSH, netcat, or web URLs
8. **Configure Hints** (optional):
   - Create progressive hints
   - Set point costs
   - Add hint prerequisites
9. **Set Branching** (optional):
   - Add prerequisites
   - Configure flag-based unlocking

#### Managing the CTF
- **Start/Stop**: Set start and end times in CTF Control
- **Pause/Resume**: Temporarily pause submissions
- **Monitor**: Dashboard shows recent activity
- **Adjust Scores**: Manual point adjustments with logging
- **View Logs**: Track all user activity and solves
- **Backups**: Automated backups with restore capability

---

## Configuration

### Platform Settings

Access via **Admin → Settings**:

1. **Event Configuration**:
   - CTF Name
   - Description
   - Logo
   - Registration toggle
   - Team mode toggle
   - First blood bonus
   - Scoreboard visibility

2. **System Settings**:
   - Timezone (16 options)
   - Backup frequency
   - Last backup time

3. **Custom Background**:
   - Enable custom CSS
   - Choose from templates
   - Live preview

### CTF Control

Access via **Admin → CTF Control**:

- **Schedule**: Set start and end times
- **Pause/Resume**: Quick control buttons
- **Status**: View current CTF state
- **Clear Schedule**: Remove time limits

### Backup Configuration

Access via **Admin → Backups**:

1. **Manual Backup**: Create instant backup
2. **Automatic Backups**: Configure frequency
   - Disabled
   - Hourly (at :00)
   - Daily (2:00 AM)
   - Weekly (Sunday 2:00 AM)
   - Monthly (1st of month, 2:00 AM)
3. **Restore**: Restore from any backup
4. **Download**: Export backup files

---

## Deployment

### Docker Deployment

```bash
# Production deployment
docker-compose -f docker-compose.yml up -d

# View logs
docker-compose logs -f blackbox

# Scale workers
docker-compose up -d --scale blackbox=4

# Update deployment
git pull
docker-compose build
docker-compose up -d
```

---

## Roadmap

### Upcoming Features

- [ ] **Multi-language Support**: Internationalization (i18n)
- [ ] **Email Notifications**: Forgot password, team invites
- [ ] **LDAP/SSO Integration**: Enterprise authentication
- [ ] **Challenge Containers**: Docker-based dynamic instances
- [ ] **Write-up Submission**: Allow participants to submit solutions
- [ ] **Badge System**: Achievements and awards
- [ ] **API Documentation**: REST API for integrations
- [ ] **Mobile App**: Native iOS/Android apps
- [ ] **Advanced Analytics**: Detailed statistics and charts
- [ ] **Export/Import**: Challenge pack sharing
- [ ] **Jeopardy Board**: Alternative challenge view
- [ ] **Attack/Defense Mode**: King-of-the-hill gameplay
- [ ] **Discord/Slack Bot**: Platform notifications
- [ ] **Certificate Generation**: Automatic CTF completion certificates

---

[⬆ Back to Top](#blackbox-ctf-platform)

</div>
