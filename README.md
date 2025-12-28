# RSPL Demo

A demo application for RSPL with FastAPI backend and HTML frontend.

## Setup

1. Create a MySQL database named `rspl_demo`.
2. Set environment variable `DATABASE_URL=mysql+pymysql://user:password@localhost/rspl_demo`
3. Install dependencies: `pip install -r backend/requirements.txt`
4. Run the backend: `uvicorn backend.main:app --reload`
5. Open frontend HTML files in browser.

## Features

- User signup and OTP verification
- KYC with Aadhaar and PAN
- Bank details
- Wallet with balance and redemption