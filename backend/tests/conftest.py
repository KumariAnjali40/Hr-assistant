import os

os.environ.setdefault("OIDC_ISSUER", "http://issuer.test/realms/hr")
os.environ.setdefault("OIDC_JWKS_URL", "http://issuer.test/jwks")
os.environ.setdefault("OIDC_AUDIENCE", "hr-assistant")
