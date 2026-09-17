import path from "node:path";
import { fileURLToPath } from "node:url";
const currentFile=fileURLToPath(import.meta.url); const currentDir=path.dirname(currentFile);
export const REPO_ROOT=path.resolve(currentDir,"../../..");
export const CREDENTIALS_PATH=process.env.GOOGLE_OAUTH_CREDENTIALS ?? path.join(REPO_ROOT,".secrets","google-oauth-credentials.json");
export const TOKEN_PATH=process.env.GOOGLE_OAUTH_TOKEN ?? path.join(REPO_ROOT,".secrets","google-token.json");
