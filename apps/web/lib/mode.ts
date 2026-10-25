export type Mode = "group" | "solo";
/** Home-page choice: go with others or alone. Read by the matches page to lead with solo. */
export const MODE_KEY = "huddleup.mode";

export function readMode(): Mode {
  try {
    return localStorage.getItem(MODE_KEY) === "solo" ? "solo" : "group";
  } catch {
    return "group";
  }
}
