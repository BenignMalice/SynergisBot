#!/usr/bin/env python3
"""
Setup Email Notifications for Trading Bot
Simple setup script for Gmail notifications
"""

import os
from dotenv import load_dotenv

def setup_email_notifications():
    """Setup email notifications in .env file"""
    
    print("Email Notification Setup")
    print("=" * 30)
    print()
    print("This will help you set up email notifications for your trading bot.")
    print("You'll need a Gmail account and an App Password.")
    print()
    
    # Get email details
    email = input("Enter your Gmail address: ").strip()
    if not email:
        print("❌ Email address is required")
        return False
    
    app_password = input("Enter your Gmail App Password (not your regular password): ").strip()
    if not app_password:
        print("❌ App Password is required")
        print("   To get an App Password:")
        print("   1. Go to Google Account settings")
        print("   2. Security > 2-Step Verification")
        print("   3. App passwords > Generate password")
        print("   4. Use the generated password here")
        return False
    
    notification_email = input("Enter notification recipient email (or press Enter to use same as sender): ").strip()
    if not notification_email:
        notification_email = email
    
    # Read current .env file
    env_path = ".env"
    env_content = ""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_content = f.read()
    
    # Add email settings
    email_settings = f"""
# Email Notifications
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER={email}
EMAIL_PASSWORD={app_password}
FROM_EMAIL={email}
NOTIFICATION_EMAIL={notification_email}
"""
    
    # Check if email settings already exist
    if "SMTP_SERVER" in env_content:
        print("⚠️ Email settings already exist in .env file")
        overwrite = input("Do you want to overwrite them? (y/N): ").strip().lower()
        if overwrite != 'y':
            print("❌ Setup cancelled")
            return False
        
        # Remove existing email settings
        lines = env_content.split('\n')
        new_lines = []
        skip_section = False
        for line in lines:
            if line.startswith('# Email Notifications'):
                skip_section = True
                continue
            elif skip_section and (line.startswith('#') or line.startswith('SMTP_') or line.startswith('EMAIL_') or line.startswith('FROM_') or line.startswith('NOTIFICATION_')):
                continue
            elif skip_section and line.strip() == '':
                continue
            else:
                skip_section = False
                new_lines.append(line)
        
        env_content = '\n'.join(new_lines)
    
    # Add new email settings
    env_content += email_settings
    
    # Write updated .env file
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print()
    print("✅ Email notifications configured!")
    print(f"   Sender: {email}")
    print(f"   Recipient: {notification_email}")
    print()
    print("Testing email notification...")
    
    # Test the configuration
    try:
        from alternative_notifications import AlternativeNotifier
        notifier = AlternativeNotifier()
        
        if notifier.email_enabled:
            success = notifier.send_email_notification(
                "Trading Bot Setup Complete",
                "Your trading bot email notifications are now configured and working!"
            )
            
            if success:
                print("✅ Test email sent successfully!")
                print("   Check your inbox for the test message.")
            else:
                print("❌ Test email failed. Please check your settings.")
        else:
            print("❌ Email configuration failed. Please check your .env file.")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

def main():
    """Main setup function"""
    print("🤖 Trading Bot Email Notification Setup")
    print("=" * 40)
    print()
    
    if setup_email_notifications():
        print()
        print("🎉 Setup complete! Your bot can now send email notifications.")
        print("   The bot will send alerts for:")
        print("   - Trade executions")
        print("   - System alerts")
        print("   - Error notifications")
        print("   - Important updates")
    else:
        print()
        print("❌ Setup failed. Please try again.")

if __name__ == "__main__":
    main()
