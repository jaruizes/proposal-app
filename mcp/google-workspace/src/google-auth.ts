import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { spawn } from "node:child_process";
import { google } from "googleapis";
import { CREDENTIALS_PATH, TOKEN_PATH } from "./paths.js";

export const SCOPES = [
  "https://www.googleapis.com/auth/drive.readonly",
  "https://www.googleapis.com/auth/drive.file",
  "https://www.googleapis.com/auth/presentations",
  "https://www.googleapis.com/auth/documents",
  "https://www.googleapis.com/auth/spreadsheets"
];

type OAuthClientConfig = {
  client_id: string;
  client_secret: string;
  redirect_uris?: string[];
};

type CredentialsJson = {
  installed?: OAuthClientConfig;
  web?: OAuthClientConfig;
};

type StoredToken = {
  type: "authorized_user";
  client_id: string;
  client_secret: string;
  refresh_token: string;
};

async function readClientConfig(): Promise<OAuthClientConfig> {
  const raw = await fs.readFile(CREDENTIALS_PATH, "utf8");
  const json = JSON.parse(raw) as CredentialsJson;
  const config = json.installed ?? json.web;

  if (!config) {
    throw new Error(
      `OAuth credentials at ${CREDENTIALS_PATH} must contain an installed or web client`
    );
  }

  return config;
}

function openBrowser(url: string): void {
  const platform = process.platform;
  const command = platform === "darwin" ? "open" : platform === "win32" ? "cmd" : "xdg-open";
  const args = platform === "win32" ? ["/c", "start", "", url] : [url];

  const child = spawn(command, args, {
    detached: true,
    stdio: "ignore"
  });
  child.unref();
}

function waitForAuthorizationCode(server: http.Server, redirectUri: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      server.close();
      reject(new Error("Timed out waiting for Google OAuth callback"));
    }, 5 * 60 * 1000);

    server.on("request", (req, res) => {
      try {
        const requestUrl = new URL(req.url ?? "/", redirectUri);
        const oauthError = requestUrl.searchParams.get("error");
        const code = requestUrl.searchParams.get("code");

        if (oauthError) {
          clearTimeout(timeout);
          res.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
          res.end(`Google OAuth failed: ${oauthError}`);
          server.close();
          reject(new Error(`Google OAuth failed: ${oauthError}`));
          return;
        }

        if (!code) {
          res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
          res.end("Waiting for OAuth callback...");
          return;
        }

        clearTimeout(timeout);
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end("<h2>Proposal Copilot authenticated.</h2><p>You can close this tab.</p>");
        server.close();
        resolve(code);
      } catch (error) {
        clearTimeout(timeout);
        server.close();
        reject(error);
      }
    });
  });
}

/**
 * Local OAuth flow implemented only with googleapis.
 *
 * This intentionally avoids @google-cloud/local-auth and a direct
 * google-auth-library dependency. Keeping a single auth implementation prevents
 * the duplicate OAuth2Client private-field TypeScript conflict that occurs when
 * packages resolve different physical versions of google-auth-library.
 */
export async function interactiveLogin(): Promise<void> {
  await fs.mkdir(path.dirname(TOKEN_PATH), { recursive: true });
  const config = await readClientConfig();

  const server = http.createServer();
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve());
  });

  const address = server.address();
  if (!address || typeof address === "string") {
    server.close();
    throw new Error("Could not allocate a local OAuth callback port");
  }

  const redirectUri = `http://127.0.0.1:${address.port}/oauth2callback`;
  const oauth2 = new google.auth.OAuth2(
    config.client_id,
    config.client_secret,
    redirectUri
  );

  const authorizationUrl = oauth2.generateAuthUrl({
    access_type: "offline",
    prompt: "consent",
    scope: SCOPES
  });

  console.log(`OAuth callback: ${redirectUri}`);
  console.log("Opening browser for Google authorization...");
  console.log(`If the browser does not open, visit:\n${authorizationUrl}\n`);
  openBrowser(authorizationUrl);

  const code = await waitForAuthorizationCode(server, redirectUri);
  const { tokens } = await oauth2.getToken(code);

  if (!tokens.refresh_token) {
    throw new Error(
      "Google did not return a refresh token. Revoke the app grant and run auth again."
    );
  }

  const token: StoredToken = {
    type: "authorized_user",
    client_id: config.client_id,
    client_secret: config.client_secret,
    refresh_token: tokens.refresh_token
  };

  await fs.writeFile(TOKEN_PATH, JSON.stringify(token, null, 2), {
    mode: 0o600
  });
}

export async function getAuth() {
  let token: StoredToken;

  try {
    token = JSON.parse(await fs.readFile(TOKEN_PATH, "utf8")) as StoredToken;
  } catch {
    throw new Error(
      `Google token not found at ${TOKEN_PATH}. Run: npm --prefix mcp/google-workspace run auth`
    );
  }

  if (!token.client_id || !token.client_secret || !token.refresh_token) {
    throw new Error(`Invalid Google token file at ${TOKEN_PATH}`);
  }

  const oauth2 = new google.auth.OAuth2(token.client_id, token.client_secret);
  oauth2.setCredentials({ refresh_token: token.refresh_token });
  return oauth2;
}
