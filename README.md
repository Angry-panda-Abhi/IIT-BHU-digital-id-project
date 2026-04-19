# 🛡️ Secure QR-Based Digital ID Card System

> A full-stack Flask web application for generating, managing, and verifying student ID cards using secure QR codes with comprehensive attack prevention mechanisms.

**Indian Institute of Technology, Varanasi · Secure Digital ID System**

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.1-green?logo=flask)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Security Features](#-security-features--attack-prevention)
- [Setup & Installation](#-setup--installation)
- [Usage Guide](#-usage-guide)
- [Database Schema](#-database-schema)
- [API Endpoints](#-api-endpoints)
- [Attack Prevention Techniques](#-attack-prevention-techniques-explained)

---

## ✨ Features

### Core Functionality
- **Admin Dashboard** — Create, update, deactivate student records with search and filters
- **Secure QR Generation** — HMAC-signed UUID tokens embedded in QR codes
- **Real-Time Verification** — Scan QR to verify identity with photo, status, and timestamp
- **PDF ID Cards** — Download styled CR80-format ID cards as PDF
- **Email QR Codes** — Send QR codes directly to student email
- **OTP-Based Recovery** — Secure QR recovery via email verification
- **Scan Logging** — Comprehensive audit trail for every verification attempt
- **Anomaly Detection** — Automatic flagging of suspicious scan patterns

### Security
- HMAC-SHA256 signed tokens
- UUID-based anti-enumeration
- Rate limiting on all sensitive endpoints
- bcrypt password hashing
- Scan anomaly detection (frequency + multi-IP)
- Expiry enforcement
- Data minimization on verification pages

---

## 🏗️ Architecture

```
ExploProject/
├── app.py                    # Flask app factory
├── config.py                 # Configuration
├── models.py                 # SQLAlchemy models (5 tables)
├── extensions.py             # Shared extensions
├── seed_admin.py             # Admin account setup
├── requirements.txt          # Dependencies
│
├── routes/
│   ├── admin.py              # Admin CRUD + auth (14 endpoints)
│   ├── verify.py             # QR verification (public)
│   └── recovery.py           # OTP recovery flow
│
├── services/
│   ├── token_service.py      # UUID + HMAC token management
│   ├── qr_service.py         # QR image generation
│   ├── pdf_service.py        # ID card PDF generation
│   ├── email_service.py      # Email (QR + OTP)
│   └── security_service.py   # Scan logging + anomaly detection
│
├── templates/                # Jinja2 HTML templates
├── static/
│   ├── css/style.css         # Complete design system
│   ├── js/                   # Frontend JavaScript
│   ├── images/               # Logo, badges
│   └── uploads/              # Student photos
│
└── instance/
    └── college_id.db         # SQLite database
```

---

## 🔒 Security Features & Attack Prevention

| Attack Vector | Prevention Mechanism |
|---|---|
| **ID Enumeration** | UUID tokens instead of sequential IDs; internal PKs never exposed |
| **QR Duplication** | Photo verification, real-time timestamps, scan logging |
| **URL Tampering** | HMAC-SHA256 digital signatures validated server-side |
| **Brute Force** | 128-bit UUID tokens + rate limiting (10 req/min per IP) |
| **Unauthorized Recovery** | OTP via registered email; max 3 OTP requests/hour |
| **Data Leakage** | Only name, course, photo, status shown; no emails/internal IDs |
| **Expired ID Misuse** | Automatic expiry checking; blocks verification for expired/inactive |
| **Fake QR Usage** | College branding, verified badge, HMAC signature validation |
| **Replay Attacks** | Scan logging detects repeated scans from multiple IPs |
| **Admin Brute Force** | bcrypt hashing + 5 login attempts/minute rate limit |

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10+ installed
- pip package manager

### Steps

```bash
# 1. Navigate to the project
cd ExploProject

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Seed the admin account
python seed_admin.py
# Output: admin / SecureAdmin@2026

# 5. Run the application
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

### Default Admin Credentials
| Field | Value |
|---|---|
| Username | `admin` |
| Password | `SecureAdmin@2026` |

> ⚠️ Change this password after first login in production!

---

## 📖 Usage Guide

### 1. Admin Login
Navigate to `/admin/login` and sign in with admin credentials.

### 2. Create Student
- Click **+ New Student** on the dashboard
- Fill in: Name, Student ID, Course, Email, Photo
- Click **Create Student & Generate QR**
- A UUID token and HMAC-signed QR code are generated automatically

### 3. Manage Students
From the dashboard, you can:
- ✏️ **Edit** — Update student details
- 📄 **Download PDF** — Get a styled ID card
- 📧 **Email QR** — Send QR to student's email
- 🔄 **Regenerate QR** — Revoke old QR, create new one
- 🗑️ **Deactivate** — Revoke QR and mark inactive

### 4. Verify Identity (QR Scan)
When a QR code is scanned, it opens:
```
/verify?token=<uuid>&sig=<hmac_signature>
```
The system:
1. Validates the HMAC signature
2. Checks the token exists and is not revoked
3. Verifies the student status and expiry
4. Displays: Name, Course, Photo, Status, Verified Badge
5. Logs the scan (IP, device, timestamp, result)
6. Checks for anomalous scan patterns

### 5. Recover Lost QR
Students can recover their QR at `/recovery/`:
1. Enter Student ID or email
2. Receive OTP via email
3. Enter OTP to verify identity
4. View/save existing QR code (no new token generated)

### 6. Monitor Scan Logs
View all verification attempts at `/admin/scan-logs` with:
- Timestamps, IP addresses, device info
- Success/invalid/expired/rate_limited results
- Pagination for large datasets

---

## 🗄️ Database Schema

### users
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Internal ID (never exposed) |
| name | VARCHAR(120) | Full name |
| student_id | VARCHAR(20) | College-issued ID (unique) |
| course | VARCHAR(100) | Program of study |
| email | VARCHAR(120) | Email (unique) |
| photo | VARCHAR(255) | Photo filename |
| status | VARCHAR(10) | active / inactive / expired |
| expiry_date | DATE | Auto-set to +1 year |

### tokens
| Column | Type | Description |
|---|---|---|
| user_id | INTEGER FK | Links to users.id (unique) |
| token | VARCHAR(64) | UUID4 hex (indexed) |
| hmac_signature | VARCHAR(128) | HMAC-SHA256 of token |
| is_revoked | BOOLEAN | Revocation flag |

### scan_logs
| Column | Type | Description |
|---|---|---|
| user_id | INTEGER FK | Nullable (for invalid scans) |
| token_used | VARCHAR(64) | Audit trail |
| ip_address | VARCHAR(45) | IPv4/IPv6 |
| user_agent | VARCHAR(512) | Browser/device info |
| result | VARCHAR(20) | success/invalid/expired/rate_limited |

### admins
| Column | Type | Description |
|---|---|---|
| username | VARCHAR(50) | Unique |
| password_hash | VARCHAR(255) | bcrypt |

### otp_requests
| Column | Type | Description |
|---|---|---|
| user_id | INTEGER FK | |
| otp_secret | VARCHAR(32) | pyotp TOTP secret |
| expires_at | DATETIME | +10 minutes |
| is_used | BOOLEAN | One-time use flag |

---

## 🔌 API Endpoints

### Public
| Method | Path | Description | Rate Limit |
|---|---|---|---|
| GET | `/` | Landing page | — |
| GET | `/verify?token=&sig=` | QR verification | 10/min |
| GET/POST | `/recovery/` | Recovery request | 3/min |
| POST | `/recovery/verify-otp` | OTP verification | 5/min |

### Admin (login required)
| Method | Path | Description | Rate Limit |
|---|---|---|---|
| GET/POST | `/admin/login` | Login | 5/min |
| GET | `/admin/logout` | Logout | — |
| GET | `/admin/dashboard` | Student list + stats | — |
| GET/POST | `/admin/students/new` | Create student | — |
| GET/POST | `/admin/students/<token>/edit` | Edit student | — |
| POST | `/admin/students/<token>/delete` | Deactivate student | — |
| POST | `/admin/students/<token>/regenerate` | Regenerate QR | — |
| GET | `/admin/students/<token>/download-pdf` | Download PDF ID | — |
| POST | `/admin/students/<token>/email-qr` | Email QR | — |
| GET | `/admin/scan-logs` | View scan logs | — |

---

## 🔐 Attack Prevention Techniques Explained

### 1. Anti-Enumeration (Preventing ID Guessing)
**Threat:** Attacker tries sequential IDs (`/verify?id=1`, `/verify?id=2`…)
**Solution:** Use 128-bit UUID4 tokens (e.g., `0a90be3e034d4eabb0414a778f65cb3e`). With 2^128 possibilities, brute-force is computationally infeasible.

### 2. HMAC Digital Signatures (Preventing Tampering)
**Threat:** Attacker modifies the token in the URL
**Solution:** Each token has an HMAC-SHA256 signature computed with a server-side secret. On verification, the server re-computes the HMAC and compares using constant-time comparison (`hmac.compare_digest`). Any modification is immediately detected.

### 3. Rate Limiting (Preventing Brute Force)
**Threat:** Automated scripts scanning thousands of random tokens
**Solution:** Flask-Limiter enforces per-IP limits: 10 verifications/minute, 5 login attempts/minute, 3 OTP requests/minute. Exceeded limits return HTTP 429 and are logged.

### 4. QR Duplication Detection
**Threat:** Attacker photographs or copies someone's QR code
**Solution:** Verification page displays the student's photo prominently, allowing visual cross-check. Real-time timestamps prevent screenshot-based impersonation. Scan logging detects the same token being scanned from multiple IP addresses within a short window.

### 5. Secure OTP Recovery
**Threat:** Attacker tries to regenerate someone's QR code
**Solution:** Recovery requires knowledge of the student ID or email AND access to the registered email inbox (OTP). OTP is TOTP-based with 10-minute expiry. Max 3 OTP requests per hour per user. The system never reveals whether a user exists (same response for valid/invalid identifiers).

### 6. Data Minimization
**Threat:** Verification page leaks sensitive information
**Solution:** Only essential data shown on verification: name, course, photo, status. Internal IDs, email addresses, and other PII are never exposed on public pages.

### 7. Expiry Enforcement
**Threat:** Student uses an expired ID card
**Solution:** Every verification checks `expiry_date` against current date. Expired IDs are automatically blocked with a clear "EXPIRED" status, regardless of database status field.

### 8. Password Security
**Threat:** Admin password compromise
**Solution:** Passwords stored as bcrypt hashes with salt. Login endpoint rate-limited to 5 attempts/minute per IP.

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12 / Flask 3.1 |
| Database | SQLite (SQLAlchemy ORM) |
| Authentication | Flask-Login + bcrypt |
| Rate Limiting | Flask-Limiter |
| QR Generation | qrcode + Pillow |
| PDF Generation | ReportLab |
| Email | Flask-Mail |
| OTP | pyotp (TOTP) |
| Crypto | HMAC-SHA256, UUID4 |
| Frontend | HTML5, CSS3, JavaScript |

---

## 📄 License

This project is for educational/academic purposes. Built to demonstrate applied cybersecurity concepts in a practical web application.

---

*Built with 🔒 security-first design by Indian Institute of Technology, Varanasi*
