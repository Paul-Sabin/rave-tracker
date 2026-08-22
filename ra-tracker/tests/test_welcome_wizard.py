"""Route-level tests for the onboarding wizard (Phase 20, plan 20-01).

These cover every success criterion in 20-01-PLAN.md, so the wizard's routing
behaviour is verified without a browser, a deployment, or a human clicking
through eight steps.
"""

import re

import pytest

STEPS = [1, 2, 3, 4]
WIZARD_GET_PATHS = ["/welcome", "/welcome/step/1", "/welcome/step/4"]


def _csrf_post_complete(client):
    """POST /welcome/complete with a valid double-submit CSRF token."""
    client.get("/welcome/step/4")  # seeds the csrftoken cookie
    token = client.cookies.get("csrftoken")
    assert token, "CSRF middleware did not set a csrftoken cookie"
    return client.post("/welcome/complete", data={"csrf_token": token})


# --- Criterion 1: /welcome redirects to the first step ---

def test_welcome_redirects_to_first_step(auth_client):
    response = auth_client.get("/welcome")
    assert response.status_code == 302
    assert response.headers["location"] == "/welcome/step/1"


# --- Criterion 2: each step renders with the right number ---

@pytest.mark.parametrize("step", STEPS)
def test_each_step_renders_its_own_number(auth_client, step):
    response = auth_client.get(f"/welcome/step/{step}")
    assert response.status_code == 200
    assert f"Step {step} of 4" in response.text


# --- Criterion 3: out-of-range steps are clamped, never 404 or 500 ---

@pytest.mark.parametrize("step", [5, 99, 1000])
def test_high_steps_clamp_to_four(auth_client, step):
    response = auth_client.get(f"/welcome/step/{step}")
    assert response.status_code == 200
    assert "Step 4 of 4" in response.text


@pytest.mark.parametrize("step", [0, -1, -99])
def test_low_steps_clamp_to_one(auth_client, step):
    response = auth_client.get(f"/welcome/step/{step}")
    assert response.status_code == 200
    assert "Step 1 of 4" in response.text


# --- Criterion 4: unauthenticated users are sent to login ---

@pytest.mark.parametrize("path", WIZARD_GET_PATHS)
def test_unauthenticated_get_redirects_to_login(client, path):
    response = client.get(path)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --- Criterion 5: authenticated but unverified users cannot enter ---

@pytest.mark.parametrize("path", WIZARD_GET_PATHS)
def test_unverified_user_redirected_to_verification(unverified_client, path):
    response = unverified_client.get(path)
    assert response.status_code == 303
    assert response.headers["location"] == "/verify-email"


# --- Criterion 6: completion persists the flag and returns to the dashboard ---

def test_complete_sets_flag_and_redirects_to_dashboard(auth_client, db, verified_user):
    assert db.get_user_by_id(verified_user.id).onboarding_completed is False

    response = _csrf_post_complete(auth_client)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert db.get_user_by_id(verified_user.id).onboarding_completed is True


def test_complete_rejected_without_csrf_token(auth_client, db, verified_user):
    response = auth_client.post("/welcome/complete", data={})
    assert response.status_code == 403
    assert db.get_user_by_id(verified_user.id).onboarding_completed is False


def test_complete_requires_authentication(client):
    response = client.post("/welcome/complete", data={})
    assert response.status_code in (303, 403)
    assert response.headers.get("location") != "/"


# --- Criterion 7: steps 1-3 offer Next, step 4 offers Complete ---

@pytest.mark.parametrize("step", [1, 2, 3])
def test_intermediate_steps_link_to_the_next_step(auth_client, step):
    response = auth_client.get(f"/welcome/step/{step}")
    assert f'href="/welcome/step/{step + 1}"' in response.text
    assert "Next" in response.text
    assert "/welcome/complete" not in response.text


def test_final_step_offers_completion_form(auth_client):
    response = auth_client.get("/welcome/step/4")
    assert 'action="/welcome/complete"' in response.text
    assert 'method="POST"' in response.text.replace("method='POST'", 'method="POST"')
    assert "Complete" in response.text
    assert ">Next<" not in response.text


# --- Walking the wizard the way a user does: follow each Next link ---

def test_next_links_walk_from_step_one_to_step_four(auth_client):
    path = "/welcome/step/1"
    for expected_step in STEPS:
        response = auth_client.get(path)
        assert response.status_code == 200
        assert f"Step {expected_step} of 4" in response.text
        if expected_step == 4:
            break
        match = re.search(r'href="(/welcome/step/\d+)"', response.text)
        assert match, f"no Next link found on step {expected_step}"
        path = match.group(1)


# --- Phase 19 regression: the column default the wizard depends on ---

def test_new_users_have_not_completed_onboarding(db):
    user_id = db.create_user("fresh@example.test", "another-long-password-1", "Fresh")
    assert db.get_user_by_id(user_id).onboarding_completed is False
