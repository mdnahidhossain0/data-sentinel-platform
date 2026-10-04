"""Live end-to-end acceptance check for the Vendor Portal -> Customer Portal flow.

Runs against two REAL running servers over HTTP (no mocks). See README, "Live end-to-end check".

    Vendor Portal   http://localhost:8001   (needs staff users: manager=LICENSE_MANAGER, viewer=VIEWER,
                                             both with password staff-pass-12345, and the Monthly/Yearly plans)
    Customer Portal http://localhost:8000
    Both need the same VENDOR_PROVISIONING_KEY; the Customer Portal needs SENTINEL_CLOUD_URL=http://localhost:8001.
"""
import re, sys, requests

V = "http://localhost:8001"
C = "http://localhost:8000"
STAFF_PW = "staff-pass-12345"
n = 0

def ok(msg):
    global n
    n += 1
    print(f"  PASS {n:02d}  {msg}")

def check(cond, msg, extra=""):
    if not cond:
        print(f"  FAIL      {msg}\n{extra}")
        sys.exit(1)
    ok(msg)

def csrf_name(s):
    if "vendor_csrftoken" in s.cookies:
        return "vendor_csrftoken"
    if "customer_csrftoken" in s.cookies:
        return "customer_csrftoken"
    raise AssertionError(f"no known CSRF cookie present yet: {dict(s.cookies)}")

def login(base, username, password):
    s = requests.Session()
    s.get(base + "/accounts/login/")
    r = s.post(base + "/accounts/login/", data={"username": username, "password": password,
               "csrfmiddlewaretoken": s.cookies[csrf_name(s)]}, allow_redirects=False)
    return s, r

def post(s, base, path, data=None, **kw):
    data = dict(data or {})
    data["csrfmiddlewaretoken"] = s.cookies[csrf_name(s)]
    return s.post(base + path, data=data, allow_redirects=False, **kw)

print("\n== 1-4. Vendor logs in, creates Customer A + Yearly license + portal login ==")
vs, r = login(V, "manager", STAFF_PW)
check(r.status_code == 302, "vendor license manager logs into Vendor Portal")
form = vs.get(V + "/customers/new/").text
plan_id = re.search(r'<option value="(\d+)"[^>]*>Yearly', form).group(1)

def create_customer(name, email, pw):
    r = post(vs, V, "/customers/new/", {"company_name": name, "email": email, "initial_password": pw,
             "plan": plan_id, "start_date": "2026-09-26", "contact_person": "Ops"})
    return r

r = create_customer("Customer A", "a@customer-a.example", "TempPass-A-123456")
check(r.status_code == 200 and "Customer created successfully" in r.text, "vendor creates Customer A (customer + license + provisioning)")
check("could not be provisioned" not in r.text, "vendor->customer-portal provisioning call succeeded over real HTTP")
check("TempPass-A-123456" in r.text, "vendor is shown the temporary password once, to relay to the customer")
check("DSK1.****" in r.text and "DSK1.ey" not in r.text, "vendor result page shows the license masked")
a_id = re.search(r"/customers/(\d+)/", r.text).group(1)
detail = vs.get(V + f"/customers/{a_id}/").text
a_lic = re.search(r"/licenses/(\d+)/", detail).group(1)
a_key = vs.get(V + f"/licenses/{a_lic}/download/").text.strip().splitlines()[-1]
check(a_key.startswith("DSK1."), "Customer A's Yearly license exists on the vendor (source of truth)")

print("\n== 5. Customer A opens the Customer Portal: no signup anywhere ==")
page = requests.get(C + "/accounts/login/").text
check(not re.search(r"sign.?up|create (an )?account|register", page, re.I), "login page has no signup / create-account / register option")
check("credentials" in page.lower() or "your vendor" in page.lower(), "login page says accounts are provisioned by the vendor")
check(requests.get(C + "/accounts/signup/").status_code == 404, "/accounts/signup/ is 404")
check(requests.post(C + "/accounts/signup/", data={"username": "x"}).status_code in (404, 403), "signup POST is not accepted")
check(requests.get(C + "/accounts/link-account/").status_code == 404, "/accounts/link-account/ is 404")
check(requests.get(C + "/", allow_redirects=False).headers["Location"].startswith("/accounts/login/"), "unauthenticated visitor is redirected to login")

print("\n== 6-8. Customer A logs in; dashboard shows Yearly / ACTIVE immediately ==")
s, bad = login(C, "a@customer-a.example", "wrong-password")
check(bad.status_code == 200, "wrong password is rejected")
sa, r = login(C, "a@customer-a.example", "TempPass-A-123456")
check(r.status_code == 302, "Customer A logs in with the vendor-provisioned credentials")
dash = sa.get(C + "/").text
check("Yearly" in dash and "ACTIVE" in dash, "dashboard immediately shows Yearly / ACTIVE (live from Vendor Cloud API)")
check("Link Your Account" not in dash and "Link Sentinel" not in dash, "no 'Link your account' state")

print("\n== 9-11. License page: masked, key absent from HTML, reveal is server-side ==")
lic = sa.get(C + "/license/").text
check("DSK1." not in lic and a_key.split(".")[1][:12] not in lic, "license key is NOT in the initial license page HTML")
check("249" in lic, "license page shows the plan price ($249)")
rv = post(sa, C, "/license/reveal/")
check(rv.status_code == 200 and rv.json()["license_key"] == a_key, "POST /license/reveal/ returns A's real key server-side")
check(requests.post(C + "/license/reveal/", allow_redirects=False).status_code in (302, 403), "reveal is refused without a session")

print("\n== 12-13. Installations and cross-customer isolation ==")
lic_b_created = create_customer("Customer B", "b@customer-b.example", "TempPass-B-123456")
check("Customer created successfully" in lic_b_created.text and "could not be provisioned" not in lic_b_created.text, "vendor creates Customer B")
b_id = re.search(r"/customers/(\d+)/", lic_b_created.text).group(1)
b_lic = re.search(r"/licenses/(\d+)/", vs.get(V + f"/customers/{b_id}/").text).group(1)
b_key = vs.get(V + f"/licenses/{b_lic}/download/").text.strip().splitlines()[-1]
check(a_key != b_key, "Customer B has a different license key")

for inst in ("aaaaaaaa-0000-0000-0000-000000000001", "aaaaaaaa-0000-0000-0000-000000000002"):
    r = requests.post(V + "/api/v1/check-in/", json={"license_key": a_key, "installation_id": inst, "agent_version": "1.0.4", "plan": "yearly"})
    check(r.json()["license_status"] == "ACTIVE", f"Data Sentinel agent {inst[-1]} checks in for A")
requests.post(V + "/api/v1/check-in/", json={"license_key": b_key, "installation_id": "bbbbbbbb-0000-0000-0000-000000000001", "agent_version": "9.9.9", "plan": "yearly"})

inst_page = sa.get(C + "/installations/").text
check("aaaaaaaa-0000-0000-0000-000000000001" in inst_page and "aaaaaaaa-0000-0000-0000-000000000002" in inst_page, "Customer A sees exactly their 2 installations")
check("bbbbbbbb" not in inst_page and "9.9.9" not in inst_page, "Customer A does NOT see Customer B's installation")
check(re.search(r"2\s*<span[^>]*>/ 2 online", sa.get(C + "/").text) is not None, "dashboard shows '2 / 2 online' installations for Customer A")

sb, r = login(C, "b@customer-b.example", "TempPass-B-123456")
check(r.status_code == 302, "Customer B logs in")
check(post(sb, C, "/license/reveal/").json()["license_key"] == b_key, "B reveals B's key (not A's)")
b_inst = sb.get(C + "/installations/").text
check("bbbbbbbb-0000-0000-0000-000000000001" in b_inst and "aaaaaaaa" not in b_inst, "Customer B sees only B's installation")

r = post(sa, C, "/support/new/", {"subject": "A private ticket", "message": "for A only", "priority": "NORMAL"})
tid = re.search(r"/support/(\d+)/", r.headers["Location"]).group(1)
check(sa.get(C + f"/support/{tid}/").status_code == 200, "Customer A can open their own ticket")
check(sb.get(C + f"/support/{tid}/").status_code == 404, "Customer B gets 404 on Customer A's ticket")
check("A private ticket" not in sb.get(C + "/support/").text, "B's ticket list does not include A's ticket")

print("\n== Provisioning endpoint cannot be used by customers ==")
r = requests.post(C + "/internal/provision/", json={"external_id": "cccccccc-0000-0000-0000-000000000009", "email": "evil@x.io", "password": "Whatever-123456"})
check(r.status_code == 401, "provisioning without the vendor key is rejected (401)")
r = sa.post(C + "/internal/provision/", json={"external_id": "cccccccc-0000-0000-0000-000000000009", "email": "evil@x.io", "password": "Whatever-123456"},
            headers={"X-CSRFToken": sa.cookies[csrf_name(sa)]})
check(r.status_code == 401, "even a logged-in customer session cannot provision accounts (401)")
r = requests.post(C + "/internal/provision/", json={"external_id": "cccccccc-0000-0000-0000-000000000009", "email": "evil@x.io", "password": "Whatever-123456"},
                  headers={"X-Vendor-Provisioning-Key": "guess"})
check(r.status_code == 401, "wrong provisioning key is rejected (401)")

print("\n== 14-15. Vendor revokes A's license / suspends B's license; portal reflects it ==")
r = post(vs, V, f"/licenses/{a_lic}/revoke/", {"reason": "FRAUD", "details": "e2e"})
check(r.status_code == 302, "vendor revokes Customer A's license")
d = sa.get(C + "/").text
check("REVOKED" in d, "Customer A's dashboard now shows REVOKED (live vendor-side change)")
check("REVOKED" in sa.get(C + "/license/").text, "Customer A's license page shows REVOKED")
post(vs, V, f"/licenses/{b_lic}/suspend/")
check("SUSPENDED" in sb.get(C + "/").text, "suspending B's license shows SUSPENDED on B's dashboard")
check("REVOKED" not in sb.get(C + "/").text, "B is unaffected by A's revocation")
check(sa.get(C + "/", allow_redirects=False).status_code == 200, "revoked LICENSE does not lock the customer out of their account (separate concept)")

print("\n== 16-17. Vendor disables A's ACCOUNT; A can no longer authenticate ==")
r = post(vs, V, f"/customers/{a_id}/suspend/")
check(r.status_code == 302, "vendor suspends Customer A's account")
r = sa.get(C + "/", allow_redirects=False)
check(r.status_code == 302 and "/accounts/login/" in r.headers["Location"], "A's existing session is invalidated on the next request")
check(sa.get(C + "/license/", allow_redirects=False).status_code == 302, "A cannot reach the license page with the old session")
check(post(sa, C, "/license/reveal/").status_code in (302, 403), "A cannot reveal the license key with the old session")
s2, r = login(C, "a@customer-a.example", "TempPass-A-123456")
check(r.status_code == 200, "fresh login with the correct password is rejected for the suspended account")
check(sb.get(C + "/", allow_redirects=False).status_code == 200, "Customer B still has access")

r = post(vs, V, f"/customers/{a_id}/reactivate/")
s3, r = login(C, "a@customer-a.example", "TempPass-A-123456")
check(r.status_code == 302, "vendor reactivates A's account -> A can log in again (password preserved, not reset by status push)")

print("\n== Vendor roles enforced over real HTTP ==")
vv, r = login(V, "viewer", STAFF_PW)
before = len(re.findall(r'href="/customers/\d+/"', vv.get(V + "/customers/").text))
r = post(vv, V, "/customers/new/", {"company_name": "Nope", "email": "nope@x.io", "initial_password": "Nope-Pass-123456", "plan": plan_id, "start_date": "2026-09-26"})
after = len(re.findall(r'href="/customers/\d+/"', vv.get(V + "/customers/").text))
check(r.status_code == 302 and before == after, "VIEWER cannot create a customer")
r = post(vv, V, f"/licenses/{b_lic}/revoke/", {"reason": "FRAUD"})
check("SUSPENDED" in sb.get(C + "/").text, "VIEWER cannot revoke a license")

print("\n== Audit trail on the vendor ==")
audit = vs.get(V + "/audit/?action=").text
for action in ("customer_created", "customer_portal_provisioned", "license_revoked", "customer_suspended",
               "customer_portal_status_synced", "cloud_check_in", "partner_api_access", "permission_denied", "login"):
    check(action in audit or action in vs.get(V + f"/audit/?action={action}").text, f"audit log contains '{action}'")

