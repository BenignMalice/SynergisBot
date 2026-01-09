import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data/auto_execution.db')
c = conn.cursor()
c.execute("SELECT conditions FROM trade_plans WHERE plan_id='chatgpt_ea35f38e'")
r = c.fetchone()
if r:
    cond = json.loads(r[0])
    print("Conditions:")
    print(json.dumps(cond, indent=2))
    
    # Validate
    issues = []
    if "price_below" not in cond and "price_above" not in cond:
        issues.append("Missing price_below/price_above")
    if "price_near" not in cond:
        issues.append("Missing price_near")
    if "tolerance" not in cond:
        issues.append("Missing tolerance")
    if cond.get("volatility_state") == "CONTRACTING":
        issues.append("volatility_state: CONTRACTING may block execution")
    
    print("\nValidation:", "OK" if not issues else ", ".join(issues))
else:
    print("Plan not found")
conn.close()

