import { interactiveLogin } from "./google-auth.js";
import { TOKEN_PATH } from "./paths.js";

console.log("Opening Google OAuth flow...");
await interactiveLogin();
console.log(`Authentication successful. Token saved to ${TOKEN_PATH}`);
