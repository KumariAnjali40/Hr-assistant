import Keycloak from "keycloak-js";

export const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:8080",
  realm: "hr",
  clientId: "hr-frontend",
});

// Authorization Code + PKCE. Tokens live in memory only (not localStorage), so XSS can't lift a long-lived token.
export async function initAuth() {
  return keycloak.init({ onLoad: "login-required", pkceMethod: "S256", checkLoginIframe: false });
}

export async function getToken() {
  await keycloak.updateToken(30); // silently refreshes when < 30s left
  return keycloak.token;
}

export const isHR = () => keycloak.hasRealmRole("hr");
export const username = () => keycloak.tokenParsed?.preferred_username;
export const logout = () => keycloak.logout({ redirectUri: window.location.origin });
