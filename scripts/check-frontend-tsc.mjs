/** Запуск tsc --noEmit в frontend (для pre-commit). */
import { execSync } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const frontend = path.join(root, "frontend");
process.chdir(frontend);
execSync("npx tsc --noEmit", { stdio: "inherit" });
