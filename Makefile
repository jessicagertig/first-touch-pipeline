.PHONY: install deploy ingest service draft test

install:
	pip install -r requirements.txt

# Deploy the Slack-interactivity Lambda. Secrets sourced from .env (never committed).
deploy:
	set -a && . ./.env && set +a && \
	sam build && \
	sam deploy --parameter-overrides \
		"SlackBotToken=$$SLACK_BOT_TOKEN" \
		"SlackSigningSecret=$$SLACK_SIGNING_SECRET" \
		"GithubOwner=$$GITHUB_OWNER" \
		"GithubRepo=$$GITHUB_REPO" \
		"GithubToken=$$GITHUB_TOKEN"

# Stage A locally: read the New Company channel, qualify, notify good leads.
ingest:
	set -a && . ./.env && set +a && python -m scripts.slack_leads_reader

# Stage B locally for one lead: make service LEAD=<lead_id>
service:
	set -a && . ./.env && set +a && python -m scripts.service_lead --lead $(LEAD)

# Stage C locally: create the Gmail draft for a chosen variation.
# make draft LEAD=<lead_id> VARIANT=<n>
draft:
	set -a && . ./.env && set +a && python -m scripts.gmail_draft --lead $(LEAD) --variant $(VARIANT)

test:
	pytest -q
