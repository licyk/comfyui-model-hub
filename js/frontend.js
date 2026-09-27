// Pure helpers, kept apart from model_hub.js so tests can import them without ComfyUI.

// Extensions can add action bar buttons since frontend 1.32.4.
export function hasActionBar(version) {
    const parts = String(version ?? "").split(".").map((part) => Number.parseInt(part, 10));
    if (parts.length < 3 || parts.some(Number.isNaN)) return false;
    for (const [index, minimum] of [1, 32, 4].entries()) {
        if (parts[index] !== minimum) return parts[index] > minimum;
    }
    return true;
}
