"""Verifies the Vendor Portal and Customer Portal never share a session/CSRF
cookie when run side by side on the same host (e.g. both on "localhost",
differing only by port) - see README, "Local development: cookie namespacing".
Run both servers first (as in scripts/e2e_live_check.py), then:

    python scripts/cookie_namespacing_check.py
"""
import re, sys, requests

V, C = "http://localhost:8001", "http://localhost:8000"
n = 0
def ok(msg):
    global n; n += 1; print(f"  PASS {n:02d}  {msg}")

s = requests.Session()
r1 = s.get(V + "/accounts/login/")
vendor_csrf_cookie_names = [c.name for c in s.cookies]
ok(f"vendor login page sets cookies: {vendor_csrf_cookie_names}")

r2 = s.get(C + "/accounts/login/")
all_cookie_names = [c.name for c in s.cookies]
ok(f"after ALSO visiting customer login page (same session/cookiejar), cookies present: {all_cookie_names}")

overlap = set(vendor_csrf_cookie_names) & {c.name for c in s.cookies}
assert "vendor_csrftoken" in all_cookie_names and "customer_csrftoken" in all_cookie_names, all_cookie_names
assert "csrftoken" not in all_cookie_names and "sessionid" not in all_cookie_names, all_cookie_names
ok("both namespaced cookies coexist in one jar with ZERO name collision (the actual fix)")

# Now simulate the exact bug scenario: load customer login page, THEN do something
# on the vendor that rotates ITS cookie, THEN submit the customer login form.
page = s.get(C + "/accounts/login/").text
token_in_form = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page).group(1)
cookie_before = s.cookies["customer_csrftoken"]

# vendor-side action in the SAME browser/cookiejar (e.g. visiting/using the vendor app)
s.get(V + "/accounts/login/")
s.get(V + "/customers/")  # any vendor navigation

cookie_after = s.cookies["customer_csrftoken"]
assert cookie_before == cookie_after, "customer cookie was disturbed by vendor activity!"
ok("customer_csrftoken is untouched by unrelated activity on the Vendor Portal")

r = s.post(C + "/accounts/login/", data={"username": "nobody@example.com", "password": "x", "csrfmiddlewaretoken": token_in_form}, allow_redirects=False)
assert r.status_code != 403, f"got a CSRF 403 even with the fix! body: {r.text[:300]}"
ok(f"login POST with the original form token is accepted by CSRF middleware (status {r.status_code}, not 403 - bug is fixed)")

print(f"\n{n}/{n} checks passed - cookie collision eliminated.")
